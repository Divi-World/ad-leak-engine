import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ad-Leak-Engine | Top 1 Global Ad Infrastructure Audit",
  description: "Enterprise-grade Meta ad infrastructure auditing and revenue recovery.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="bg-zinc-950 text-zinc-100 antialiased min-h-screen">
        <main className="container mx-auto px-4 py-8 max-w-6xl">
          {children}
        </main>
      </body>
    </html>
  );
}
