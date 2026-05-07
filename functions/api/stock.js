/**
 * Cloudflare Pages Function
 * GET /api/stock?codes=003220,003850,...
 * 네이버 금융 integration API 프록시 (주가 + 시총 + PER)
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

  const headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
    'Referer': 'https://m.stock.naver.com/',
    'Accept': 'application/json',
  };

  try {
    const results = await Promise.allSettled(
      codeList.map(code =>
        fetch(`https://m.stock.naver.com/api/stock/${code}/integration`, { headers })
          .then(r => r.json())
          .then(d => ({ code, d }))
      )
    );

    const data = {};
    for (const r of results) {
      if (r.status !== 'fulfilled') continue;
      const { code, d } = r.value;

      // 현재가 / 등락
      const price      = parseInt((d.closePrice || '0').replace(/,/g, ''), 10);
      const change     = parseInt((d.compareToPreviousClosePrice || '0').replace(/,/g, ''), 10);
      const changeRate = parseFloat(d.fluctuationsRatio || 0);

      // totalInfos에서 시총 / PER 추출
      const infos = d.totalInfos || [];
      const getInfo = (code) => infos.find(i => i.code === code)?.value || '';

      const marketValueRaw = getInfo('marketValue'); // e.g. "2,288억"
      // PER: 실적PER 우선, N/A면 추정PER 사용
      const perRaw   = getInfo('per');    // e.g. "15.04배" or "N/A"
      const cnsPerRaw = getInfo('cnsPer'); // e.g. "15.04배"
      const perStr = (perRaw && perRaw !== 'N/A') ? perRaw : cnsPerRaw;
      const per = perStr ? parseFloat(perStr.replace(/[^0-9.]/g, '')) : 0;

      data[code] = {
        price,
        change,
        changeRate,
        marketValue: marketValueRaw,   // 이미 포맷된 문자열 (예: "2,288억")
        per,
        perLabel: perStr ? perStr : '—',
      };
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
