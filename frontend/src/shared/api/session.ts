type RefreshFn = () => Promise<string | null>;
type LogoutFn = () => void;

let refreshFn: RefreshFn | null = null;
let logoutFn: LogoutFn | null = null;
let inflightRefresh: Promise<string | null> | null = null;

export function registerSessionHandlers(handlers: {
  refresh: RefreshFn;
  logout: LogoutFn;
}) {
  refreshFn = handlers.refresh;
  logoutFn = handlers.logout;
}

export function clearSessionHandlers() {
  refreshFn = null;
  logoutFn = null;
}

export async function tryRefreshAccessToken(): Promise<string | null> {
  if (!refreshFn) {
    return null;
  }
  if (inflightRefresh) {
    return inflightRefresh;
  }
  inflightRefresh = (async () => {
    try {
      return await refreshFn!();
    } catch {
      return null;
    } finally {
      inflightRefresh = null;
    }
  })();
  return inflightRefresh;
}

export function dispatchUnauthorized() {
  logoutFn?.();
}
