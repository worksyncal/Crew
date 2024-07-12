from __future__ import annotations

import asyncio
import json
import os
import platform
from typing import TYPE_CHECKING, Any

import pkg_resources
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

if TYPE_CHECKING:
    from crewai.crew import Crew
    from crewai.task import Task


class Telemetry:
    """A class to handle anonymous telemetry for the crewai package.

    The data being collected is for development purpose, all data is anonymous.

    There is NO data being collected on the prompts, tasks descriptions
    agents backstories or goals nor responses or any data that is being
    processed by the agents, nor any secrets and env vars.

    Data collected includes:
    - Version of crewAI
    - Version of Python
    - General OS (e.g. number of CPUs, macOS/Windows/Linux)
    - Number of agents and tasks in a crew
    - Crew Process being used
    - If Agents are using memory or allowing delegation
    - If Tasks are being executed in parallel or sequentially
    - Language model being used
    - Roles of agents in a crew
    - Tools names available

    Users can opt-in to sharing more complete data suing the `share_crew`
    attribute in the Crew class.
    """

    def __init__(self):
        self.ready = False
        self.trace_set = False
        try:
            telemetry_endpoint = "https://telemetry.crewai.com:4319"
            self.resource = Resource(
                attributes={SERVICE_NAME: "crewAI-telemetry"},
            )
            self.provider = TracerProvider(resource=self.resource)

            processor = BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=f"{telemetry_endpoint}/v1/traces",
                    timeout=30,
                )
            )

            self.provider.add_span_processor(processor)
            self.ready = True
        except BaseException as e:
            if isinstance(
                e,
                (SystemExit, KeyboardInterrupt, GeneratorExit, asyncio.CancelledError),
            ):
                raise  # Re-raise the exception to not interfere with system signals
            self.ready = False

    def set_tracer(self):
        if self.ready and not self.trace_set:
            try:
                trace.set_tracer_provider(self.provider)
                self.trace_set = True
            except Exception:
                self.ready = False
                self.trace_set = False

    def crew_creation(self, crew: Crew, inputs: dict[str, Any] | None):
        """Records the creation of a crew."""
        if self.ready:
            try:
                tracer = trace.get_tracer("crewai.telemetry")
                span = tracer.start_span("Crew Created")
                self._add_attribute(
                    span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                self._add_attribute(span, "python_version", platform.python_version())
                self._add_attribute(span, "crew_key", crew.key)
                self._add_attribute(span, "crew_id", str(crew.id))

                if crew.share_crew:
                    self._add_attribute(
                        span, "crew_inputs", json.dumps(inputs) if inputs else None
                    )

                self._add_attribute(span, "crew_process", crew.process)
                self._add_attribute(span, "crew_memory", crew.memory)
                self._add_attribute(span, "crew_number_of_tasks", len(crew.tasks))
                self._add_attribute(span, "crew_number_of_agents", len(crew.agents))
                self._add_attribute(
                    span,
                    "crew_agents",
                    json.dumps(
                        [
                            {
                                "key": agent.key,
                                "id": str(agent.id),
                                "role": agent.role,
                                "goal": agent.goal,
                                "backstory": agent.backstory,
                                "verbose?": agent.verbose,
                                "max_iter": agent.max_iter,
                                "max_rpm": agent.max_rpm,
                                "i18n": agent.i18n.prompt_file,
                                "llm": json.dumps(self._safe_llm_attributes(agent.llm)),
                                "delegation_enabled?": agent.allow_delegation,
                                "tools_names": [
                                    tool.name.casefold() for tool in agent.tools or []
                                ],
                            }
                            for agent in crew.agents
                        ]
                    ),
                )
                self._add_attribute(
                    span,
                    "crew_tasks",
                    json.dumps(
                        [
                            {
                                "key": task.key,
                                "id": str(task.id),
                                "description": task.description,
                                "expected_output": task.expected_output,
                                "async_execution?": task.async_execution,
                                "human_input?": task.human_input,
                                "agent_role": task.agent.role if task.agent else "None",
                                "agent_key": task.agent.key if task.agent else None,
                                "context": (
                                    [task.description for task in task.context]
                                    if task.context
                                    else None
                                ),
                                "tools_names": [
                                    tool.name.casefold() for tool in task.tools or []
                                ],
                            }
                            for task in crew.tasks
                        ]
                    ),
                )
                self._add_attribute(span, "platform", platform.platform())
                self._add_attribute(span, "platform_release", platform.release())
                self._add_attribute(span, "platform_system", platform.system())
                self._add_attribute(span, "platform_version", platform.version())
                self._add_attribute(span, "cpus", os.cpu_count())

                if crew.share_crew:
                    self._add_attribute(
                        span, "crew_inputs", json.dumps(inputs) if inputs else None
                    )

                span.set_status(Status(StatusCode.OK))
                span.end()
            except Exception:
                pass

    def task_started(self, crew: Crew, task: Task) -> Span | None:
        """Records task started in a crew."""
        if self.ready:
            try:
                tracer = trace.get_tracer("crewai.telemetry")

                created_span = tracer.start_span("Task Created")

                self._add_attribute(created_span, "crew_key", crew.key)
                self._add_attribute(created_span, "crew_id", str(crew.id))
                self._add_attribute(created_span, "task_key", task.key)
                self._add_attribute(created_span, "task_id", str(task.id))

                if crew.share_crew:
                    self._add_attribute(
                        created_span, "formatted_description", task.description
                    )
                    self._add_attribute(
                        created_span, "formatted_expected_output", task.expected_output
                    )

                created_span.set_status(Status(StatusCode.OK))
                created_span.end()

                span = tracer.start_span("Task Execution")

                self._add_attribute(span, "crew_key", crew.key)
                self._add_attribute(span, "crew_id", str(crew.id))
                self._add_attribute(span, "task_key", task.key)
                self._add_attribute(span, "task_id", str(task.id))

                if crew.share_crew:
                    self._add_attribute(span, "formatted_description", task.description)
                    self._add_attribute(
                        span, "formatted_expected_output", task.expected_output
                    )

                return span
            except Exception:
                pass

        return None

    def task_ended(self, span: Span, task: Task):
        """Records task execution in a crew."""
        if self.ready:
            try:
                self._add_attribute(
                    span, "task_output", task.output.raw_output if task.output else ""
                )

                span.set_status(Status(StatusCode.OK))
                span.end()
            except Exception:
                pass

    def tool_repeated_usage(self, llm: Any, tool_name: str, attempts: int):
        """Records the repeated usage 'error' of a tool by an agent."""
        if self.ready:
            try:
                tracer = trace.get_tracer("crewai.telemetry")
                span = tracer.start_span("Tool Repeated Usage")
                self._add_attribute(
                    span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                self._add_attribute(span, "tool_name", tool_name)
                self._add_attribute(span, "attempts", attempts)
                if llm:
                    self._add_attribute(
                        span, "llm", json.dumps(self._safe_llm_attributes(llm))
                    )
                span.set_status(Status(StatusCode.OK))
                span.end()
            except Exception:
                pass

    def tool_usage(self, llm: Any, tool_name: str, attempts: int):
        """Records the usage of a tool by an agent."""
        if self.ready:
            try:
                tracer = trace.get_tracer("crewai.telemetry")
                span = tracer.start_span("Tool Usage")
                self._add_attribute(
                    span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                self._add_attribute(span, "tool_name", tool_name)
                self._add_attribute(span, "attempts", attempts)
                if llm:
                    self._add_attribute(
                        span, "llm", json.dumps(self._safe_llm_attributes(llm))
                    )
                span.set_status(Status(StatusCode.OK))
                span.end()
            except Exception:
                pass

    def tool_usage_error(self, llm: Any):
        """Records the usage of a tool by an agent."""
        if self.ready:
            try:
                tracer = trace.get_tracer("crewai.telemetry")
                span = tracer.start_span("Tool Usage Error")
                self._add_attribute(
                    span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                if llm:
                    self._add_attribute(
                        span, "llm", json.dumps(self._safe_llm_attributes(llm))
                    )
                span.set_status(Status(StatusCode.OK))
                span.end()
            except Exception:
                pass

    def crew_execution_span(self, crew: Crew, inputs: dict[str, Any] | None):
        """Records the complete execution of a crew.
        This is only collected if the user has opted-in to share the crew.
        """
        self.crew_creation(crew, inputs)

        if (self.ready) and (crew.share_crew):
            try:
                self.crew_creation(crew, inputs)

                tracer = trace.get_tracer("crewai.telemetry")
                span = tracer.start_span("Crew Execution")
                self._add_attribute(
                    span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                self._add_attribute(span, "crew_key", crew.key)
                self._add_attribute(span, "crew_id", str(crew.id))
                self._add_attribute(
                    span, "crew_inputs", json.dumps(inputs) if inputs else None
                )
                self._add_attribute(
                    span,
                    "crew_agents",
                    json.dumps(
                        [
                            {
                                "key": agent.key,
                                "id": str(agent.id),
                                "role": agent.role,
                                "goal": agent.goal,
                                "backstory": agent.backstory,
                                "verbose?": agent.verbose,
                                "max_iter": agent.max_iter,
                                "max_rpm": agent.max_rpm,
                                "i18n": agent.i18n.prompt_file,
                                "llm": json.dumps(self._safe_llm_attributes(agent.llm)),
                                "delegation_enabled?": agent.allow_delegation,
                                "tools_names": [
                                    tool.name.casefold() for tool in agent.tools or []
                                ],
                            }
                            for agent in crew.agents
                        ]
                    ),
                )
                self._add_attribute(
                    span,
                    "crew_tasks",
                    json.dumps(
                        [
                            {
                                "id": str(task.id),
                                "description": task.description,
                                "expected_output": task.expected_output,
                                "async_execution?": task.async_execution,
                                "human_input?": task.human_input,
                                "agent_role": task.agent.role if task.agent else "None",
                                "agent_key": task.agent.key if task.agent else None,
                                "context": (
                                    [task.description for task in task.context]
                                    if task.context
                                    else None
                                ),
                                "tools_names": [
                                    tool.name.casefold() for tool in task.tools or []
                                ],
                            }
                            for task in crew.tasks
                        ]
                    ),
                )
                return span
            except Exception:
                pass

    def end_crew(self, crew, final_string_output):
        if (self.ready) and (crew.share_crew):
            try:
                self._add_attribute(
                    crew._execution_span,
                    "crewai_version",
                    pkg_resources.get_distribution("crewai").version,
                )
                self._add_attribute(
                    crew._execution_span, "crew_output", final_string_output
                )
                self._add_attribute(
                    crew._execution_span,
                    "crew_tasks_output",
                    json.dumps(
                        [
                            {
                                "id": str(task.id),
                                "description": task.description,
                                "output": task.output.raw_output,
                            }
                            for task in crew.tasks
                        ]
                    ),
                )
                crew._execution_span.set_status(Status(StatusCode.OK))
                crew._execution_span.end()
            except Exception:
                pass

    def _add_attribute(self, span, key, value):
        """Add an attribute to a span."""
        try:
            return span.set_attribute(key, value)
        except Exception:
            pass

    def _safe_llm_attributes(self, llm):
        attributes = ["name", "model_name", "base_url", "model", "top_k", "temperature"]
        if llm:
            safe_attributes = {k: v for k, v in vars(llm).items() if k in attributes}
            safe_attributes["class"] = llm.__class__.__name__
            return safe_attributes
        return {}
