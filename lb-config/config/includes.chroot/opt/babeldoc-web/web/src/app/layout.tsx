import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "TransKeep",
  description: "PDF translation that preserves layout, powered by BabelDOC",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        <header className="border-b bg-white px-6 py-3 shadow-sm">
          <div className="mx-auto flex max-w-5xl items-center justify-between">
            <Link
              href="/"
              className="inline-flex items-center gap-2.5 text-lg font-bold tracking-tight text-brand-600 transition-colors hover:text-brand-700"
            >
              <svg className="h-7 w-7" viewBox="0 0 32 32" fill="none">
                <rect x="2" y="5" width="10" height="14" rx="1.5" fill="currentColor" opacity="0.15" />
                <rect x="2" y="5" width="10" height="14" rx="1.5" stroke="currentColor" strokeWidth="1.6" />
                <line x1="4.5" y1="9" x2="9.5" y2="9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="4.5" y1="12" x2="9.5" y2="12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="4.5" y1="15" x2="7.5" y2="15" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                <path d="M14 12h4m0 0l-1.5-1.5M18 12l-1.5 1.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <rect x="20" y="5" width="10" height="14" rx="1.5" fill="currentColor" />
                <line x1="22.5" y1="9" x2="27.5" y2="9" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="22.5" y1="12" x2="27.5" y2="12" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
                <line x1="22.5" y1="15" x2="25.5" y2="15" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              <span>TransKeep</span>
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              <Link href="/" className="text-gray-600 hover:text-brand-600">
                Dịch mới
              </Link>
              <Link href="/jobs" className="text-gray-600 hover:text-brand-600">
                Lịch sử
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
