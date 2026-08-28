import "./globals.css";

export const metadata = {
  title: "Gypsi — The Round Table",
  description: "Autonomous options-trading agent with an independent risk gate on every trade.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
