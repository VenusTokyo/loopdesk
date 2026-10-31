# Self-hosting on open weights

LoopDesk has no hard dependency on any hosted model. The whole stack can run
on hardware you control.

## The provider interface

```python
class LLMProvider(Protocol):
    name: str
    def vision_json(self, system: str, user: str, image_b64: str | None, schema: dict) -> dict: ...
    def embed(self, text: str) -> list[float]: ...
```

Two methods. Everything else — retrieval, the confidence gate, ticketing,
drafting — is provider-agnostic.

## Option 1: Ollama on your own machine

```bash
ollama pull gemma3:12b
ollama pull bge-small
```

```ini
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=http://localhost:11434/v1
OPENAI_COMPAT_MODEL=gemma3:12b
OPENAI_COMPAT_EMBED_MODEL=bge-small
```

Restart and re-seed so embeddings are regenerated with the new model:

```bash
python -m backend.seed.seed --reset
```

Embeddings from different models are not comparable. Always re-seed after
switching.

## Option 2: DigitalOcean serverless inference

DigitalOcean serves open-weight models behind an OpenAI-compatible API, so
the provider LoopDesk already has works unchanged - no GPU to manage, no
droplet to keep alive.

```ini
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=https://inference.do-ai.run/v1
OPENAI_COMPAT_API_KEY=<model access key from the DO control panel>
OPENAI_COMPAT_MODEL=openai-gpt-oss-120b
```

Create the model access key in the DigitalOcean control panel, not an API
token: they are different credentials.

Two things to check on the day rather than trust:

1. **Availability.** This has been offered under more than one name
   (Gradient AI Platform, Inference) and parts of it have been in preview.
2. **Model ids.** They change. List what your key can call:

```bash
curl -H "Authorization: Bearer $KEY" https://inference.do-ai.run/v1/models
```

Then confirm LoopDesk can use it:

```bash
python -m backend.agent.check_provider
```

If the catalogue has no embedding model, keep embeddings on another provider
or fall back to the page-based suggestions, which need no vectors at all.

## Option 3: vLLM on a GPU droplet

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model google/gemma-3-12b-it --port 8001
```

```ini
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=http://your-droplet:8001/v1
OPENAI_COMPAT_MODEL=google/gemma-3-12b-it
```

Keep the endpoint on a private network or behind an API key — it accepts
screenshots.

## Option 4: offline

`LLM_PROVIDER=mock` needs nothing at all. It does real keyword overlap against
the retrieved candidates, so the confidence gate behaves sensibly: it answers
the seeded Billing and Projects bugs and refuses the unseeded Analytics one.
Good for CI and for a demo with no network.

Its limit is the obvious one: keyword overlap is not comprehension. A report
that describes a known problem in entirely different words ("the filter will
not stay where I put it" against a solution titled "date range resets") can
score just under the gate and be sent to the ticket path. That is the gate
working as designed on a weak model, not a bug — but it is why the layer-1
page suggestions matter, and why a real model is worth configuring.

## Data that stays yours

| Data | Where it goes |
|---|---|
| Screenshots | `./data/screenshots` locally, or your own private bucket |
| Reports, ratings, tickets | your database |
| Knowledge base | your database and `solutions/*.md` in your repository |
| Prompts | `backend/agent/prompts/`, plain markdown |

With `openai_compat` pointed at your own endpoint and `STORAGE_BACKEND=local`,
nothing leaves your infrastructure.

## A Gemma quirk worth knowing

Gemma models served through the Gemini API reject `responseMimeType:
"application/json"` with *"JSON mode is not enabled for models/gemma-..."*
(HTTP 400), even though Gemini models accept it. LoopDesk detects a `gemma-`
model id and omits the flag; the system prompt asks for JSON anyway and the
response is parsed leniently, so nothing else changes.

Model ids move. Settle it with your own key:

```bash
python -m backend.agent.check_provider --list
```

## Adding a provider

Create `backend/agent/providers/yours.py` with a class exposing `name`,
`vision_json` and `embed`, then register it in `providers/__init__.py`. That
is the entire change — about forty lines.
