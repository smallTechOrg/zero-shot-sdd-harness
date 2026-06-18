import AgentTrace from "@/components/AgentTrace";
import ChartView from "@/components/ChartView";
import ResultTableView from "@/components/ResultTable";
import type { Message } from "@/lib/api";

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`} data-testid={`msg-${message.role}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 ${
          isUser ? "bg-blue-600 text-white" : "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {!isUser && message.result_table ? <ResultTableView table={message.result_table} /> : null}
        {!isUser && message.chart ? <ChartView chart={message.chart} /> : null}
        {!isUser && message.trace ? <AgentTrace steps={message.trace} /> : null}
      </div>
    </div>
  );
}
