"""STEP1 통합 노이즈 필터 — vertical_keyword_extraction + 홈트 소형용품 학습 샘플."""
from __future__ import annotations

import unittest

from app.services.keyword_noise import clear_brand_noise_cache, is_step1_noise

TRAINING_NOISE_KEYWORDS = [
    "갤럭시워치울트라케이스",
    "갤럭시워치7케이스",
    "키티그립톡",
    "픽디자인거치대",
    "플립4케이스",
    "폴드4케이스",
    "폴드5케이스",
    "갤럭시워치8케이스",
    "플립7케이스",
    "플립5케이스",
    "제트플립7케이스",
    "지플립7케이스",
    "플립6케이스",
    "갤럭시워치울트라스트랩",
    "애플워치케이스",
    "워치8스트랩",
    "갤럭시케이스",
    "폴드6케이스",
    "갤럭시워치7스트랩",
    "갤럭시폴드7케이스",
    "갤럭시워치충전기",
    "어메이즈핏빕6",
    "아이폰16프로케이스",
    "갤럭시핏3스트랩",
    "샤오미워치",
    "폴드7케이스",
    "갤럭시워치8스트랩",
    "아이폰17프로케이스",
    "갤럭시핏",
    "갤럭시워치스트랩",
    "아이폰17케이스",
    "가민포러너165",
    "갤럭시워치울트라",
    "가민포러너265",
    "갤럭시워치7",
    "가민스마트워치",
    "스마트워치",
    "갤럭시핏3",
    "가민",
    "갤럭시워치",
    "애플워치",
    "갤럭시워치8",
    "케이스티파이",
    "샤오미셀카봉",
    "셀루미",
    "모모스틱",
    "헬로키티그립톡",
    "리디킬스프레이",
    "리디킬",
    "키엘세제",
    "글로썸",
    "솜솜라이크",
    "쉬슬러액체세제",
    "테크액체세제",
    "은나노스텝시즌4",
    "오미노비앙코세제",
    "파인솔",
    "유한락스곰팡이",
    "참그린주방세제",
    "멜라루카주방세제",
    "크리넥스센터풀",
    "유한킴벌리점보롤",
    "퍼실세탁세제",
    "카포드캡슐세제",
    "부활세제",
    "퍼실캡슐세제",
    "프로쉬주방세제",
    "블랑코클리닝",
    "아스토니쉬바닥클리너",
    "아스토니쉬곰팡이",
    "프릴주방세제",
    "커클랜드세제",
]

# 홈트·소형용품 브랜드 노이즈 (2026-05 추출 학습)
HOME_TRAINING_NOISE_KEYWORDS = [
    "룰루레몬매트",
    "만두카요가매트",
    "만두카요가타월",
    "만두카프로라이트",
    "만두카요가매트프로",
    "만두카프로",
    "토삭스",
    "토삭스양말",
    "트리거포인트폼롤러",
    "세라밴드플렉스바",
    "식스패드",
    "블랙롤",
    "이고진매트",
    "이고진벤치",
    "에르고바디",
    "코어바디폼롤러",
    "고무나라폼롤러",
    "고무나라풀업밴드",
    "고무나라루프밴드",
    "뷰릿",
    "스포틀러폼롤러",
    "슬렌더톤",
    "라이폼요가매트",
    "지브라매트",
    "코미밴드",
    "밸런스파워",
    "밸런스파워복근",
    "바풀슬로스바",
    "에카코어슈즈",
    "퍼펙트슬라이드",
    "에이비슬라이드",
    "코시차임",
]

KEEP_KEYWORDS = [
    "주방세제",
    "수납함",
    "텀블러",
    "휴대폰거치대",
    "가성비수납함",
    "제습기",
    "방향제",
]

HOME_KEEP_KEYWORDS = [
    "요가매트",
    "폼롤러",
    "풀업밴드",
    "홈트",
    "필라테스",
    "요가블럭",
    "저항밴드",
]


class TestStep1NoiseFilter(unittest.TestCase):
    def setUp(self) -> None:
        clear_brand_noise_cache()

    def test_training_samples_are_noise(self) -> None:
        missed = [kw for kw in TRAINING_NOISE_KEYWORDS if not is_step1_noise(kw)]
        self.assertEqual(missed, [], f"should be noise: {missed}")

    def test_home_training_samples_are_noise(self) -> None:
        missed = [kw for kw in HOME_TRAINING_NOISE_KEYWORDS if not is_step1_noise(kw)]
        self.assertEqual(missed, [], f"should be noise: {missed}")

    def test_generic_keywords_kept(self) -> None:
        blocked = [kw for kw in KEEP_KEYWORDS if is_step1_noise(kw)]
        self.assertEqual(blocked, [], f"should pass: {blocked}")

    def test_empty_is_noise(self) -> None:
        self.assertTrue(is_step1_noise(""))
        self.assertTrue(is_step1_noise("   "))

    def test_home_generic_keywords_kept(self) -> None:
        blocked = [kw for kw in HOME_KEEP_KEYWORDS if is_step1_noise(kw)]
        self.assertEqual(blocked, [], f"should pass: {blocked}")

    def test_informational_suffix_is_noise(self) -> None:
        self.assertTrue(is_step1_noise("텀블러란?"))
        self.assertTrue(is_step1_noise("주방세제사용법"))


if __name__ == "__main__":
    unittest.main()
