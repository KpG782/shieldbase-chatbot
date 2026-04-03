export const AUTH_STORAGE_KEY = "shieldbase-authenticated";

export function getConfiguredCredentials() {
  return {
    username: process.env.NEXT_PUBLIC_SHIELDBASE_LOGIN_USER || "admin",
    password: process.env.NEXT_PUBLIC_SHIELDBASE_LOGIN_PASS || "shieldbase123"
  };
}
