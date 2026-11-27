import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { MarketProvider } from "@/hooks/useMarketContext";
import { MarketAnalysisPage } from "@/pages/MarketAnalysisPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OverviewPage } from "@/pages/OverviewPage";
import { PaperTradingPage } from "@/pages/PaperTradingPage";
import { RiskManagementPage } from "@/pages/RiskManagementPage";
import { SignalIntelligencePage } from "@/pages/SignalIntelligencePage";
import { TradeJournalPage } from "@/pages/TradeJournalPage";
import "@/styles/index.css";

const queryClient = new QueryClient();
const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Missing root element");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <MarketProvider>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/overview" replace />} />
              <Route path="overview" element={<OverviewPage />} />
              <Route path="market-analysis" element={<MarketAnalysisPage />} />
              <Route path="signal-intelligence" element={<SignalIntelligencePage />} />
              <Route path="risk-management" element={<RiskManagementPage />} />
              <Route path="paper-trading" element={<PaperTradingPage />} />
              <Route path="trade-journal" element={<TradeJournalPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </MarketProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
