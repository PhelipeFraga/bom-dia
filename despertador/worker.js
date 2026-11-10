// Despertador do robô do Bom dia (Cloudflare Worker, plano grátis).
// O agendamento do GitHub pula passagens (rodava 3 a 4 vezes por dia em vez de 48), então
// o Cloudflare, que cumpre horário, pede ao GitHub para rodar o robô de hora em hora.
// Instalado à mão no painel do Cloudflare; este arquivo é só a cópia do código.
// Precisa do segredo GITHUB_TOKEN: chave do GitHub limitada ao repositório bom-dia, com Actions (leitura e escrita).
// Agendamento (Triggers → Cron): 50 * * * *  (aos 50 de cada hora, horário UTC)

export default {
  async scheduled(evento, env, ctx) {
    ctx.waitUntil(acordarRobo(env));
  },
};

async function acordarRobo(env) {
  const r = await fetch(
    "https://api.github.com/repos/PhelipeFraga/bom-dia/actions/workflows/coletar.yml/dispatches",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "bom-dia-despertador",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  // 204 = o GitHub aceitou e o robô começa em seguida
  if (r.status !== 204) console.log("GitHub recusou:", r.status, await r.text());
}
