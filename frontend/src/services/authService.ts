import { api } from "@/lib/api";

export async function loginAccessToken(params: { username: string; password: string }) {
  const body = new URLSearchParams();
  body.set("username", params.username);
  body.set("password", params.password);

  const { data } = await api.post<{ accessToken: string; tokenType: string }>(
    "/auth/login/access-token",
    body,
    { headers: { "Content-Type": "application/x-www-form-urlencoded" } },
  );
  return data;
}
