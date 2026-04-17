import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { ThemeProvider } from "./context/ThemeProvider";
import Navbar from "./components/Navbar";
import Home from "./pages/Home";
import Dashboard from "./pages/Dashboard";
import IngestDashboard from "./pages/IngestDashboard";
import AdminData from "./pages/AdminData";
import TermsOfService from "./pages/TermsOfService";
import PrivacyPolicy from "./pages/PrivacyPolicy";

export default function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen bg-slate-50 dark:bg-[#05080f] transition-colors duration-300">
        <BrowserRouter>
          <Navbar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/player/:region/:gameName/:tagLine" element={<Dashboard />} />
            <Route path="/admin/ingest" element={<IngestDashboard />} />
            <Route path="/admin/data" element={<AdminData />} />
            <Route path="/terms" element={<TermsOfService />} />
            <Route path="/privacy" element={<PrivacyPolicy />} />
          </Routes>
        </BrowserRouter>
        <SpeedInsights />
      </div>
    </ThemeProvider>
  );
}
