"use client";
import dynamic from "next/dynamic";

const HomePageClient = dynamic(() => import("./HomePageClient"), { ssr: false });

export default function Page() {
  return <HomePageClient />;
}
