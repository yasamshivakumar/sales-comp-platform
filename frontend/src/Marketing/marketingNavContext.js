import { createContext, useContext } from "react";

export const MarketingNavContext = createContext(null);

export function useMarketingNav() {
  const context = useContext(MarketingNavContext);
  if (!context) {
    throw new Error("useMarketingNav must be used within MarketingLayout");
  }
  return context;
}
