import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Multilingual Voice AI",
  description:
    "Real-time multilingual conversational voice assistant: Groq Whisper STT, Google Gemini LLM, ElevenLabs TTS. Speak in your language, get a human-like reply.",
  keywords: [
    "voice AI",
    "multilingual",
    "speech to text",
    "text to speech",
    "Gemini",
    "Groq Whisper",
    "ElevenLabs",
    "Next.js",
    "FastAPI",
  ],
  authors: [{ name: "Multilingual Voice AI" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "Multilingual Voice AI",
    description:
      "Speak in English, Hindi, Telugu and more — get a human-like spoken reply.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Multilingual Voice AI",
    description:
      "Speak in English, Hindi, Telugu and more — get a human-like spoken reply.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
