/**
 * Cloudflare Pages Function
 * GET /api/stock?codes=003220,003850,...
 * 네이버 모바일 주식 API 프록시 (주가 + 시총 + PER)
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

  const codeList = codes.split(',').map(c => c.trim()).filter(Boolean);

  try {
    // 네이버 모바일 basic API - 종목별 병렬 요청
    const results = await Promise.allSettled(
      codeList.map(code =>
        fetch(`https://m.stock.naver.com/api/stock/${code}/basic`, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
            'Referer': 'https://m.stock.naver.com/',
            'Accept': 'application/json',
          },
        }).then(r => r.json()).then(d => ({ code, d }))
      )
    );

    const data = {};
    for (const r of results) {
      if (r.status !== 'fulfilled') continue;
      const { code, d } = r.value;

      const price      = parseInt(d.closePrice?.replace(/,/g, '') || 0, 10);
      const change     = parseInt(d.compareToPreviousClosePrice?.replace(/,/g, '') || 0, 10);
      const changeRate = parseFloat(d.fluctuationsRatio || 0);
      const marketCap  = parseInt(d.marketValue?.replace(/,/g, '') || 0, 10);   // 원 단위
      const per        = parseFloat(d.per || 0);

      data[code] = { price, change, changeRate, marketCap, per };
    }

    return new Response(JSON.stringify({ ok: true, data }), { headers: CORS });

  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: e.message }), { status: 500, headers: CORS });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
    },
  });
}
