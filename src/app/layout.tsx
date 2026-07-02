import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SchedulerProvider } from "@/components/SchedulerProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "VoC Turknet",
  description:
    "TürkNet müşteri yorumlarını toplayan, yapay zeka ile analiz eden ve merkezi raporlayan Voice of Customer dashboard.",
  keywords: ["customer voice", "dashboard", "türknet", "sentiment analysis", "AI"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="tr"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block"
        />
      </head>
      <body className="min-h-full flex flex-col">
        <SchedulerProvider />
        {children}
      </body>
    </html>
  );
}

