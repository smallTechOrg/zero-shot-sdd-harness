import "./globals.css";

export const metadata = {
  title: "Data Analysis Agent",
  description: "Upload datasets and query them in natural language",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        {/* Plotly loaded from CDN — no SSR issue */}
        <script
          src="https://cdn.plot.ly/plotly-2.35.2.min.js"
          charSet="utf-8"
        />
      </head>
      <body className="bg-gray-50 min-h-screen">{children}</body>
    </html>
  );
}
