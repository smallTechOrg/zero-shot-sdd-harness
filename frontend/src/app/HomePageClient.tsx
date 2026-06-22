"use client";
import { useState, useEffect } from "react";
import { StubBanner } from "./components/StubBanner";
import { DatasetSidebar } from "./components/DatasetSidebar";
import { ChatPanel } from "./components/ChatPanel";
import type { Message } from "./components/ChatPanel";
import { apiClient } from "./lib/apiClient";
import type { DatasetMeta, QueryResult } from "./lib/types";

export default function HomePage() {
  const [stubMode, setStubMode] = useState(false);
  const [datasets, setDatasets] = useState<DatasetMeta[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isQuerying, setIsQuerying] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .getCurrentSession()
      .then((session) => {
        setStubMode(session.stub_mode ?? false);
        setDatasets(session.datasets ?? []);
        const restored: Message[] = session.conversation.map((turn) => ({
          role: turn.role,
          content: turn.content,
          sql: turn.sql,
          timestamp: turn.timestamp,
        }));
        setMessages(restored);
      })
      .catch(() =>
        setSessionError("Could not load your session. Refresh to start a new one.")
      );
  }, []);

  const handleUpload = async (file: File) => {
    setUploadError(null);
    setIsUploading(true);
    try {
      const meta = await apiClient.uploadDataset(file);
      setDatasets((prev) => {
        const idx = prev.findIndex((d) => d.original_filename === meta.original_filename);
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = meta;
          return next;
        }
        return [...prev, meta];
      });
    } catch (err: unknown) {
      const e = err as { code?: string; status?: number; message?: string };
      if (e.status === 400) {
        if (e.code === "invalid_file") {
          setUploadError(e.message ?? "Invalid file.");
        } else {
          setUploadError(`Upload failed: ${e.message}`);
        }
      } else {
        setUploadError("Upload failed. Please try again.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleQuery = async (question: string) => {
    setIsQuerying(true);
    const userMsg: Message = {
      role: "user",
      content: question,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    try {
      const result: QueryResult = await apiClient.query(question);
      const assistantMsg: Message = {
        role: "assistant",
        content: `Returned ${result.row_count} row(s).`,
        sql: result.sql,
        result,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const e = err as { code?: string; status?: number; message?: string };
      let errorText = e.message || "An unexpected error occurred.";
      if (e.status === 502) {
        errorText = "Could not reach the AI service. Please try again in a moment.";
      } else if (e.status === 422 && e.code === "sql_rejected") {
        errorText = "The AI returned an unsafe query. Try rephrasing your question.";
      } else if (e.status === 422 && e.code === "no_datasets") {
        errorText = "No dataset loaded. Please upload a file first.";
      } else if (e.status === 422 && e.code === "unknown_table") {
        errorText = "The query referenced a table that isn't in your session. Please re-upload the dataset.";
      } else if (e.status === 422 && e.code === "question_too_long") {
        errorText = "Question is too long. Please shorten it.";
      } else if (e.status === 504) {
        errorText = "The query took too long to run. Try a more specific question.";
      }
      const assistantMsg: Message = {
        role: "assistant",
        content: errorText,
        error: errorText,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setIsQuerying(false);
    }
  };

  if (sessionError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-red-600 text-center max-w-sm">{sessionError}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <StubBanner stubMode={stubMode} />
      <div className="flex flex-1 overflow-hidden">
        <DatasetSidebar
          datasets={datasets}
          isUploading={isUploading}
          uploadError={uploadError}
          onUpload={handleUpload}
        />
        <ChatPanel
          messages={messages}
          hasDatasets={datasets.length > 0}
          isQuerying={isQuerying}
          onSubmit={handleQuery}
        />
      </div>
    </div>
  );
}
