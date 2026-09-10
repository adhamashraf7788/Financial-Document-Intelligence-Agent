from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import retrieve_node, prepare_retry_node, reason_node, decide_next_step

builder = StateGraph(AgentState)
builder.add_node("retrieve", retrieve_node)
builder.add_node("prepare_retry", prepare_retry_node)
builder.add_node("reason", reason_node)

builder.set_entry_point("retrieve")
builder.add_conditional_edges("retrieve", decide_next_step, {"retry": "prepare_retry", "reason": "reason"})
builder.add_edge("prepare_retry", "retrieve")
builder.add_edge("reason", END)

agent_graph = builder.compile()
