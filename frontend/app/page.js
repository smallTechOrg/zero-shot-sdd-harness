"use client";
// Disable SSR for the chat app — it uses browser-only APIs (localStorage, Plotly CDN).
import dynamic from "next/dynamic";

const ChatPage = dynamic(() => import("./ChatPage"), { ssr: false });

export default function Page() {
  return <ChatPage />;
}
