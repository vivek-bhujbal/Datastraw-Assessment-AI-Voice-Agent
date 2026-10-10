import asyncio
import base64
import json

import httpx
import pytest

from app.agent import Agent
from app.config import Settings
from app.llm import GeminiLLM
from app.session import call_error
from app.voice import GeminiVoice
from test_rules import outcome, wav


def sse(events, status='completed'):
    events = [*events, {'event_type': 'interaction.completed', 'interaction': {'status': status}}]
    body = ''.join('data: ' + json.dumps(event) + '\n\n' for event in events) + 'data: [DONE]\n\n'
    return httpx.Response(200, content=body, headers={'content-type': 'text/event-stream'})


def event(kind, index, value):
    return {'event_type': 'step.' + kind, 'index': index, 'step' if kind == 'start' else 'delta': value}


async def mock_client(provider, handler):
    await provider.client.close()
    provider.client.client = httpx.AsyncClient(
        base_url='https://generativelanguage.googleapis.com/v1beta/',
        headers={'x-goog-api-key': 'test-only'}, transport=httpx.MockTransport(handler)
    )


def test_gemini_transcription_and_streamed_pcm_requests():
    async def run():
        seen = []
        def handler(request):
            data = json.loads(request.content)
            seen.append(data)
            assert request.url.path == '/v1beta/interactions'
            assert request.headers['x-goog-api-key'] == 'test-only'
            assert data['store'] is False
            if data['model'] == 'gemini-3.5-flash-lite':
                assert data['generation_config']['thinking_level'] == 'low'
                assert data['input'][0]['mime_type'] == 'audio/wav'
                assert base64.b64decode(data['input'][0]['data']) == wav()
                assert data['response_format']['schema']['required'] == ['text']
                return httpx.Response(200, json={'status': 'completed', 'steps': [
                    {'type': 'model_output', 'content': [{'type': 'text', 'text': '{"text":"Where is ORD-101?"}'}]}
                ]})
            assert data['model'] == 'gemini-3.8-flash-lite-tts'
            assert data['response_format'] == {'type': 'audio', 'mime_type': 'audio/l16', 'sample_rate': 24000}
            assert data['generation_config']['speech_config'] == [{'voice': 'Kore'}]
            assert data['input'][0]['content'][0]['text'] == 'Hello'
            return sse([event('start', 0, {'type': 'model_output'}),
                        event('delta', 0, {'type': 'audio', 'mime_type': 'audio/l16', 'data': base64.b64encode(b'\x00\x00' * 2400).decode()})])
        voice = GeminiVoice(Settings(gemini_api_key='test-only'))
        await mock_client(voice, handler)
        assert await voice.transcribe(wav()) == 'Where is ORD-101?'
        assert len(b''.join([chunk async for chunk in voice.speech('Hello')])) == 4800
        assert len(seen) == 2
        await voice.close()
    asyncio.run(run())


def test_gemini_fragmented_function_call_preserves_signature_and_context():
    async def run():
        requests, records = [], []
        def handler(request):
            data = json.loads(request.content)
            requests.append(data)
            assert data['stream'] is True and data['store'] is False
            assert data['generation_config']['thinking_level'] == 'low'
            assert data['tools'][0]['name'] == 'get_order_details'
            if len(requests) == 1:
                return sse([
                    event('start', 0, {'type': 'thought'}),
                    event('delta', 0, {'type': 'thought_signature', 'signature': 'keep-this-signature'}),
                    event('start', 1, {'type': 'function_call', 'id': 'call_1', 'name': 'get_order_details', 'arguments': {}}),
                    event('delta', 1, {'type': 'arguments_delta', 'arguments': '{"order_id":'}),
                    event('delta', 1, {'type': 'arguments_delta', 'arguments': '"ORD-101"}'}),
                ], 'requires_action')
            assert data['input'][1] == {'type': 'thought', 'signature': 'keep-this-signature'}
            assert data['input'][2]['arguments'] == {'order_id': 'ORD-101'}
            result = data['input'][-1]
            assert result['type'] == 'function_result' and result['call_id'] == 'call_1'
            assert json.loads(result['result'][0]['text'])['courier'] == 'BlueDart'
            return sse([event('start', 0, {'type': 'model_output'}),
                        event('delta', 0, {'type': 'text', 'text': 'Your order is out for delivery. '}),
                        event('delta', 0, {'type': 'text', 'text': 'BlueDart expects it by 6 PM today.'})])
        llm = GeminiLLM(Settings(gemini_api_key='test-only'))
        await mock_client(llm, handler)
        async def record(name, result): records.append(result)
        replies = [reply async for reply in Agent(llm, record).answer('Where is ORD-101?')]
        assert replies == ['Your order is out for delivery.', 'BlueDart expects it by 6 PM today.']
        assert records[0]['found'] is True
        await llm.close()
    asyncio.run(run())


def test_gemini_structured_summary_schema():
    async def run():
        def handler(request):
            data = json.loads(request.content)
            assert data['response_format']['mime_type'] == 'application/json'
            assert data['generation_config']['thinking_level'] == 'low'
            assert 'resolution_status' in data['response_format']['schema']['required']
            return httpx.Response(200, json={'status': 'completed', 'steps': [
                {'type': 'model_output', 'content': [{'type': 'text', 'text': json.dumps(outcome())}]}
            ]})
        llm = GeminiLLM(Settings(gemini_api_key='test-only'))
        await mock_client(llm, handler)
        result = await llm.summary([{'role': 'user', 'content': 'Summarise'}])
        assert result.order_ids == ['ORD-101']
        await llm.close()
    asyncio.run(run())


@pytest.mark.parametrize('status', [400, 403, 404, 429, 503])
def test_provider_http_errors_are_actionable(status):
    async def run():
        def handler(request):
            return httpx.Response(status, json={'error': {'message': 'API key not valid.'}})
        voice = GeminiVoice(Settings(gemini_api_key='test-only'))
        await mock_client(voice, handler)
        with pytest.raises(httpx.HTTPStatusError) as error:
            await voice.transcribe(wav())
        assert call_error(error.value, 'Generic failure') != 'Generic failure'
        await voice.close()
    asyncio.run(run())


def test_incomplete_audio_stream_is_rejected():
    async def run():
        voice = GeminiVoice(Settings(gemini_api_key='test-only'))
        def handler(request):
            body = 'data: ' + json.dumps(event('delta', 0, {'type': 'audio', 'data': 'AAA='})) + '\n\n'
            return httpx.Response(200, content=body, headers={'content-type': 'text/event-stream'})
        await mock_client(voice, handler)
        with pytest.raises(ValueError, match='interrupted'):
            await collect(voice.speech('Hello'))
        await voice.close()
    asyncio.run(run())


async def collect(stream):
    return [item async for item in stream]


def test_daily_quota_error_explains_reset_without_replacing_the_key():
    request = httpx.Request('POST', 'https://generativelanguage.googleapis.com/v1beta/interactions')
    response = httpx.Response(429, request=request, json={'error': {
        'message': 'Rate limit exceeded for model gemini-3.8-flash-tts (limit: 10 requests per day on Free Tier).'
    }})
    error = httpx.HTTPStatusError('Rate limit exceeded', request=request, response=response)
    message = call_error(error, 'Generic failure')
    assert 'daily reset' in message
    assert 'does not need to be replaced' in message


@pytest.mark.parametrize('streamed', [False, True])
def test_temporary_provider_error_is_retried_once(streamed):
    async def run():
        voice = GeminiVoice(Settings(gemini_api_key='test-only'))
        attempts = 0
        def handler(request):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(503, json={'error': {'message': 'Service unavailable'}})
            if streamed:
                return sse([event('delta', 0, {'type': 'audio', 'data': 'AAA='})])
            return httpx.Response(200, json={'status': 'completed', 'steps': [
                {'type': 'model_output', 'content': [{'type': 'text', 'text': '{"text":"Hello"}'}]}
            ]})
        await mock_client(voice, handler)
        if streamed:
            assert b''.join(await collect(voice.speech('Hello'))) == b'\x00\x00'
        else:
            assert await voice.transcribe(wav()) == 'Hello'
        assert attempts == 2
        await voice.close()
    asyncio.run(run())
