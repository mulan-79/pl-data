/**
 * Cloudflare Pages Function
 * GET /api/stock?codes=003220,003850,...
 * 네이버 금융 실시간 주가 프록시
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
    return new Response(JSON.stringify({ error: 'codes 파라미터 필요 (예: ?codes=003220,003850)' }), {
      status: 400, headers: CORS,
    });
  }

  try {
    // 네이버 금융 실시간 polling API (다중 종목)
    const naverUrl = `https://polling.finance.naver.com/api/realtime/domestic/stock?codes=${codes}`;
    const res = await fetch(naverUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://finance.naver.com/',
        'Accept': 'application/json, text/plain, */*',
      },
    });

    if (!res.ok) throw new Error(`네이버 API 오류: ${res.status}`);

    const raw = await res.json();

    // 응답 정규화: { stockCode: { price, change, changeRate, marketStatus } }
    const result = {};
    const stocks = raw?.result?.stocks || raw?.stocks || raw || {};

    for (const [code, info] of Object.entries(stocks)) {
      const s = info?.dealTrendInfoDto || info?.stockDto || info || {};
      result[code] = {
        price:       parseInt(s.closePrice        || s.currentPrice || s.nv  || 0, 10),
        change:      parseInt(s.compareToPreviousClosePrice || s.cv || 0, 10),
        changeRate:  parseFloat(s.fluctuationsRatio || s.cr || 0),
        status:      s.marketStatus || s.marketCondition || '',
      };
    }

    return new Response(JSON.stringify({ ok: true, data: result }), { headers: CORS });

  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: e.message }), {
      status: 500, headers: CORS,
    });
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
