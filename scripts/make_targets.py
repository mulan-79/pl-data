"""scripts/targets.json 생성: 경쟁사 12곳 + 코스닥·상장사 65곳 (종목코드 6자리)."""
import json, os

COMPETITORS = """보령 003850, JW중외제약 001060, 일동제약 249420, 대원제약 003220, 한독 002390, 동화약품 000020, 삼진제약 005500, 한국유나이티드제약 033270, 영진약품 003520, 경보제약 214390, 일양약품 007570, 신풍제약 019170"""

TARGETS65 = """삼성바이오로직스 207940, 셀트리온 068270, 유한양행 000100, 종근당 185750, 녹십자 006280, 대웅제약 069620, 한미약품 128940, HK이노엔 195940, 광동제약 009290, 보령 003850, 동국제약 086450, JW중외제약 001060, 동아에스티 170900, 제일약품 271980, 일동제약 249420, 대원제약 003220, 휴온스 243070, 셀트리온제약 068760, 한독 002390, 파마리서치 214450, 콜마비앤에이치 200130, 동화약품 000020, 씨젠 096530, 안국약품 001540, 삼진제약 005500, 한국유나이티드제약 033270, 휴젤 145020, 영진약품 003520, 경보제약 214390, 환인제약 016580, 일양약품 007570, JW생명과학 234080, 동구바이오제약 006620, 하나제약 293480, 메디톡스 086900, 신풍제약 019170, 삼일제약 000520, 에스티팜 237690, 대한뉴팜 054670, 대한약품 023910, 알리코제약 260660, 코오롱생명과학 102940, 경동제약 011040, 티앤엘 340570, 팜젠사이언스 004720, 테라젠이텍스 066700, 명문제약 017180, 바이넥스 053030, 종근당바이오 063160, 국제약품 002720, 휴메딕스 200670, 부광약품 003000, 에이비엘바이오 298380, 한올바이오파마 009420, 유바이오로직스 206650, 삼천당제약 000250, 이연제약 102460, 바디텍메드 206640, 국전약품 307750, 동국생명과학 303810, 알피바이오 314140, SK바이오사이언스 302440, 녹십자웰빙 234690, 진양제약 007370, 바이오노트 377740"""


def parse(s):
    out = []
    for item in s.split(','):
        name, code = item.strip().rsplit(' ', 1)
        out.append({'code': code, 'name': name})
    return out


comp = parse(COMPETITORS)
targets = parse(TARGETS65)
assert len(comp) == 12, len(comp)
assert len({t['code'] for t in targets}) == len(targets), 'duplicate codes in targets'
missing = {c['code'] for c in comp} - {t['code'] for t in targets}
assert not missing, f'competitors not in targets65: {missing}'

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'targets.json'), 'w', encoding='utf-8') as f:
    json.dump({'competitors': comp, 'targets': targets}, f, ensure_ascii=False, indent=1)
print(f'competitors {len(comp)} / targets {len(targets)}')
