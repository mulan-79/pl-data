/**
 * Cloudflare Pages Function
 * GET /api/stock?codes=003220,003850,...
 * 네이버 금융 프록시 (주가: basic + 시총/PER: integration 병렬)
 */
export async function onRequestGet(context) {
  const CORS = {
    'Access-Control-Allow-Origin': '*',
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store',
  };

  const url = new URL(context.request.url);
  const codes = url.searchParams.get('codes') || '';
  if (!codes) {
    return new Response(JSON.stringify({ error: 'codes 파라미터 필요' }), { status: 400, headers: CORS });
  }

  // 6자리 zero-padding
  const codeList = codes.split(',').map(c => c.trim().padStart(6, '0')).filter(Boolean);

  const hdrs = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
    'Referer': 'https://m.stock.naver.com/',
    'Accept': 'application/json',
  };

  const fetchJSON = (url) => fetch(url, { headers: hdrs }).then(r => r.ok ? r.json() : null).catch(() => null);

  try {
    // 종목별로 basic + integration 병렬 요청
    const results = await Promise.all(
      codeList.map(async code => {
        const [basic, integ] = await Promise.all([
          fetchJSON(`https://m.stock.naver.com/api/stock/${code}/basic`),
          fetchJSON(`https://m.stock.naver.com/api/stock/${code}/integration`),
        ]);
        return { code, basic, integ };
      })
    );

    const data = {};
    for (const { code, basic, integ } of results) {
      if (!basic && !integ) continue;

      // ── 현재가 (basic) ──
      const price      = parseInt((basic?.closePrice || '0').replace(/,/g, ''), 10);
      const change     = parseInt((basic?.compareToPreviousClosePrice || '0').replace(/,/g, ''), 10);
      const changeRate = parseFloat(basic?.fluctuationsRatio || 0);

      // ── 시총 / PER (integration → totalInfos) ──
      const infos = integ?.totalInfos || [];
      const getInfo = key => infos.find(i => i.code === key)?.value || '';

      const marketValue = getInfo('marketValue');          // "2,288억"
      const perRaw      = getInfo('per');                  // "15.04배" or "N/A"
      const cnsPerRaw   = getInfo('cnsPer');               // 추정PER
      const perStr      = (perRaw && perRaw !== 'N/A') ? perRaw : cnsPerRaw;
      const per         = perStr ? parseFloat(perStr.replace(/[^0-9.]/g, '')) : 0;

      data[code] = { price, change, changeRate, marketValue, per };
    }

    return new Response(JSON.stringify({ ok: true, data }), { headers: CORS });

  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 500, headers: CORS });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, OPTIONS' },
  });
}
