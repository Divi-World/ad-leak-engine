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
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var t=localStorage.getItem('ale_theme')||'dark';var f=localStorage.getItem('ale_font')||'base';if(t==='dark')document.documentElement.classList.add('dark');document.documentElement.style.fontSize=f==='small'?'14px':f==='large'?'18px':'16px';}catch(e){}})()` }} />
      </head>
      <body className="bg-[var(--background)] text-[var(--foreground)] antialiased min-h-screen transition-colors">
        <main className="container mx-auto px-4 py-8 max-w-6xl">
          {children}
        </main>
      </body>
    </html>
  );
}
