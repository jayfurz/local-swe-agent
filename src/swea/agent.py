"""Wire a HarnessConfig to an Agents SDK Agent backed by a local endpoint."""

from __future__ import annotations

from agents import (
    Agent,
    AsyncOpenAI,
    ModelSettings,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

from .config import HarnessConfig
from .prompt import SYSTEM_PROMPT
from .tools import ALL_TOOLS, Workspace


def build_agent(cfg: HarnessConfig) -> Agent[Workspace]:
    # No OpenAI key in play: without this the SDK tries to upload traces and 401s.
    set_tracing_disabled(True)
    # Local servers can wedge mid-run; without a client timeout a dead request
    # hangs the whole task. 180s still allows slow cold model loads.
    client = AsyncOpenAI(base_url=cfg.base_url, api_key=cfg.api_key,
                         timeout=180.0, max_retries=1)
    return Agent[Workspace](
        name="swea",
        instructions=SYSTEM_PROMPT,
        model=OpenAIChatCompletionsModel(model=cfg.model, openai_client=client),
        # Leave every other ModelSettings field None so it is omitted from the
        # request — strict local servers reject params they don't implement.
        model_settings=ModelSettings(temperature=cfg.temperature),
        tools=ALL_TOOLS,
    )
