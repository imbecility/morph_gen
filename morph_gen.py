from argparse import ArgumentParser
from dataclasses import dataclass
from json import dump
from pathlib import Path
from sys import exit, argv, stderr

from pymorphy3 import MorphAnalyzer
from yaml import safe_load, safe_dump

HUSH = set('гкхжчшщ')

SCHEMAS = {
    'masc_cons': {
        'sing': {'nomn': '', 'gent': 'а', 'datv': 'у', 'accs': None, 'ablt': 'ом', 'loct': 'е'},
        'plur': {'nomn': 'ы', 'gent': 'ов', 'datv': 'ам', 'accs': None, 'ablt': 'ами', 'loct': 'ах'}
    },
    'masc_fleeting_ok': {
        'sing': {'nomn': 'ок', 'gent': 'ка', 'datv': 'ку', 'accs': None, 'ablt': 'ком', 'loct': 'ке'},
        'plur': {'nomn': 'ки', 'gent': 'ков', 'datv': 'кам', 'accs': None, 'ablt': 'ками', 'loct': 'ках'}
    },
    'masc_fleeting_ol': {
        'sing': {'nomn': 'ол', 'gent': 'ла', 'datv': 'лу', 'accs': None, 'ablt': 'лом', 'loct': 'ле'},
        'plur': {'nomn': 'лы', 'gent': 'лов', 'datv': 'лам', 'accs': None, 'ablt': 'лами', 'loct': 'лах'}
    },
    'masc_y': {
        'sing': {'nomn': 'й', 'gent': 'я', 'datv': 'ю', 'accs': None, 'ablt': 'ем', 'loct': 'е'},
        'plur': {'nomn': 'и', 'gent': 'ев', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
    'masc_soft': {
        'sing': {'nomn': 'ь', 'gent': 'я', 'datv': 'ю', 'accs': None, 'ablt': 'ем', 'loct': 'е'},
        'plur': {'nomn': 'и', 'gent': 'ей', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
    'fem_a': {
        'sing': {'nomn': 'а', 'gent': 'ы', 'datv': 'е', 'accs': 'у', 'ablt': 'ой', 'loct': 'е'},
        'plur': {'nomn': 'ы', 'gent': '', 'datv': 'ам', 'accs': None, 'ablt': 'ами', 'loct': 'ах'}
    },
    'fem_ya': {
        'sing': {'nomn': 'я', 'gent': 'и', 'datv': 'е', 'accs': 'ю', 'ablt': 'ей', 'loct': 'е'},
        'plur': {'nomn': 'и', 'gent': 'ь', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
    'fem_ia': {
        'sing': {'nomn': 'ия', 'gent': 'ии', 'datv': 'ии', 'accs': 'ию', 'ablt': 'ией', 'loct': 'ии'},
        'plur': {'nomn': 'ии', 'gent': 'ий', 'datv': 'иям', 'accs': None, 'ablt': 'иями', 'loct': 'иях'}
    },
    'neut_o': {
        'sing': {'nomn': 'о', 'gent': 'а', 'datv': 'у', 'accs': 'о', 'ablt': 'ом', 'loct': 'е'},
        'plur': {'nomn': 'а', 'gent': '', 'datv': 'ам', 'accs': 'а', 'ablt': 'ами', 'loct': 'ах'}
    },
    'neut_e': {
        'sing': {'nomn': 'е', 'gent': 'я', 'datv': 'ю', 'accs': 'е', 'ablt': 'ем', 'loct': 'е'},
        'plur': {'nomn': 'я', 'gent': 'ей', 'datv': 'ям', 'accs': 'я', 'ablt': 'ями', 'loct': 'ях'}
    },
    'neut_ie': {
        'sing': {'nomn': 'ие', 'gent': 'ия', 'datv': 'ию', 'accs': 'ие', 'ablt': 'ием', 'loct': 'ии'},
        'plur': {'nomn': 'ия', 'gent': 'ий', 'datv': 'иям', 'accs': 'ия', 'ablt': 'иями', 'loct': 'иях'}
    },
    'neut_mia': {
        'sing': {'nomn': 'мя', 'gent': 'мени', 'datv': 'мени', 'accs': 'мя', 'ablt': 'менем', 'loct': 'мени'},
        'plur': {'nomn': 'мена', 'gent': 'мен', 'datv': 'менам', 'accs': 'мена', 'ablt': 'менами', 'loct': 'менах'}
    },
    'fem_soft': {
        'sing': {'nomn': 'ь', 'gent': 'и', 'datv': 'и', 'accs': 'ь', 'ablt': 'ью', 'loct': 'и'},
        'plur': {'nomn': 'и', 'gent': 'ей', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
}

# приоритеты падежей для плоского словаря: чем выше число, тем важнее форма.
# чтобы loc2 не перезаписывал datv
CASE_PRIORITY = {
    'nomn': 10,
    'gent': 9,
    'datv': 8,
    'ablt': 7,
    'loct': 6,
    'accs': 5,
    'voct': 4,
    'loc2': 3,
    'gen2': 2
}

EXAMPLE_YAML = '''
- source: гурманство
  target: гортанобесие
- source: гнилец
  target: нурглит
- source: жаба
  target: ропуха
- source: мешкожаберный
  target: клариевый
'''.strip()


@dataclass(frozen=True)
class FormRow:
    """
    структура для хранения одной сгенерированной формы слова.

    Attributes:
        source (str): исходная форма слова (например, "кота").
        target (str): целевая форма слова (например, "нурглита").
        tag (str): морфологический тег pymorphy3, описывающий форму.
    """
    source: str
    target: str
    tag: str


class NounDecliner:
    """
    принудительно склоняет существительные по заданным схемам,
    игнорируя словарь pymorphy для целевого слова.

    Note:
        схемы окончаний (SCHEMAS) определены на уровне модуля (Singular, Plural).
        ключи падежей: (nomn, gent, datv, accs, ablt, loct).
        значение None в accs означает, что падеж вычисляется динамически по одушевленности.
    """

    @staticmethod
    def classify(word: str) -> tuple[str, str]:
        """
        определяет тип склонения и основу слова (stem) на основе эвристики окончаний.

        Args:
            word (str): слово в именительном падеже, единственном числе (лемма).

        Returns:
            tuple[str, str]: кортеж, содержащий тип склонения (ключ из SCHEMAS) и основу слова.
                если слово несклоняемое, возвращается ('indeclinable', word).
        """

        # базовая эвристика окончания на гласную
        if word.endswith(('у', 'ю', 'э', 'о', 'е', 'и')):
            # слово считается склоняемым если оканчивается на гласную, даже если не попадает в стандартные паттерны
            if word.endswith(('у', 'э')):
                return 'indeclinable', word
            if word.endswith('и') and not word.endswith('ии'):
                return 'indeclinable', word

        # стандартные окончания
        if word.endswith('ия'): return 'fem_ia', word[:-2]
        if word.endswith('ие'): return 'neut_ie', word[:-2]
        # разносклоняемые на -мя
        if word.endswith('мя'):
            # обычно -мя это neut_mia
            return 'neut_mia', word[:-2]
        # беглые гласные (ок -> к, ол -> л)
        # проверка длинны > 3, чтобы не ломать короткие слова (ток, гол)
        if len(word) > 3:
            if word.endswith('ок') and word[-3] not in 'аяуюиыеёоэ':
                return 'masc_fleeting_ok', word[:-2]
            if word.endswith('ол') and word[-3] not in 'аяуюиыеёоэ':
                return 'masc_fleeting_ol', word[:-2]
            # TODO: далеко не везде гласная выпадает: боец -> бойца (е -> й), это сложно
            if word.endswith('ец') and word[-3] not in 'аяуюиыеёоэ':
                return 'masc_fleeting_ec', word[:-2]

        if word.endswith('а'):  return 'fem_a', word[:-1]
        if word.endswith('я'):  return 'fem_ya', word[:-1]
        if word.endswith('о'):  return 'neut_o', word[:-1]
        if word.endswith('е'):  return 'neut_e', word[:-1]

        # й
        if word.endswith('й'):  return 'masc_y', word[:-1]

        # ь
        if word.endswith('ь'):
            stem = word[:-1]
            # ж, ш, ч, щ -> fem (рожь, мышь)
            if stem and stem[-1] in 'жшчщ':
                return 'fem_soft', stem
            # суффиксы
            # обычные зять/тать - сюда не попадут, они известны pymorphy
            if word.endswith(('ость', 'есть', 'знь', 'дь', 'вать')):
                return 'fem_soft', stem
            # ь
            return 'masc_soft', stem

        # согласная
        return 'masc_cons', word

    @classmethod
    def decline(cls, lemma: str, case: str, number: str, animate: bool, src_tag=None) -> str:
        """
        склоняет лемму по заданному падежу и числу, используя внутренние схемы.

        Args:
            lemma (str): лемма целевого слова.
            case (str): требуемый падеж (например, 'gent', 'datv').
            number (str): требуемое число ('sing' или 'plur').
            animate (bool): флаг одушевленности, влияет на винительный падеж.
            src_tag (Tag | None, optional): морфологический тег исходного слова.
                используется для спец-логики (например, мужские имена на -я) и вариативности.
                по умолчанию None.

        Returns:
            str: сгенерированная форма слова.

        Raises:
            RuntimeError: если тип склонения неизвестен или требуемое число не поддерживается схемой.
        """
        # нормализация падежей через pymorphy
        case_map = {'gen2': 'gent', 'loc2': 'loct', 'voct': 'nomn'}
        case = case_map.get(case, case)

        decl_type, stem = cls.classify(lemma)

        if decl_type not in SCHEMAS:
            if decl_type == 'indeclinable': return stem
            raise RuntimeError(f'тип склонения для {lemma} неизвестен')

        schema = SCHEMAS[decl_type].get(number)
        if not schema:
            raise RuntimeError(f'номер "{number}" не поддерживается для типа "{decl_type}"')

        # базовое окончание
        ending = schema.get(case)

        # Спец-логика для Родительного мн.ч. мужских имен на -я (Костя -> Костей)
        # Если схема "женская" (fem_ya), но исходное слово было Мужского рода,
        # меняем окончание 'ь' (Бань) на 'ей' (Дядей, Костей).
        if decl_type == 'fem_ya' and number == 'plur' and case == 'gent':
            # Проверяем род исходника. Если Константин (masc) -> Костя, то Костей.
            if src_tag and 'masc' in src_tag:
                ending = 'ей'

        # винительный падеж (если None, то зависит от одушевленности)
        if case == 'accs' and ending is None:
            # для одушевленных винительный = родительный, иначе винительный = именительный
            eff_case = 'gent' if animate else 'nomn'
            ending = schema[eff_case]

        # обработка вариативности (V-tags из source)
        # пример: творительный падеж -ой/-ою для fem_a
        vm = get_v_markers(src_tag) if src_tag else set()
        if case == 'ablt':
            if decl_type == 'fem_a' and 'V-oy' in vm:
                ending = 'ою'
            elif decl_type == 'fem_ya' and 'V-ey' in vm:
                ending = 'ею'
            elif decl_type == 'fem_ia' and 'V-ieyu' in vm:
                ending = 'иею'

        # сборка слова с учетом орфографии
        if ending is None:
            raise RuntimeError(f'не найдено окончание для {decl_type} {case} {number}')

        return apply_orthography(stem, ending)


class PairGenerator:
    """
    генератор морфологических пар, использующий pymorphy3 для сопоставления
    форм исходного слова с формами целевого слова.

    поддерживает фолбек на ручной склонятель (NounDecliner) для неизвестных существительных.
    """

    def __init__(self):
        """
        инициализирует анализатор pymorphy3, пытаясь найти словари
        в порядке: встроенные данные (после компилляции nuitka), внешняя папка, стандартная установка.

        Raises:
            SystemExit: если словари pymorphy3 не найдены ни в одном из ожидаемых мест.
        """
        # поиск папки словарей
        # nuitka с --include-data-dir положит папку сюда:
        internal_path = get_internal_data_dir() / 'pymorphy_data'
        # вариант с папкой рядом с исполняемым файлом:
        external_path = get_exe_dir() / 'pymorphy_data'

        self.morph = None

        if internal_path.exists():
            # сначала вшитые словари
            self.morph = MorphAnalyzer(path=str(internal_path))
        elif external_path.exists():
            # фолбек: внешняя папка
            self.morph = MorphAnalyzer(path=str(external_path))
        else:
            # фолбек: стандартная установка (запуск скрипта без компилляции)
            try:
                self.morph = MorphAnalyzer()
            except Exception:  # noqa
                print(f'[ОШИБКА] словари нигде не найдены!', file=stderr)
                exit(1)

        self._target_cache = {}

    def get_source_parses(self, lemma: str):
        """
        получает список подходящих разборов (парадигм) для исходной леммы.

        фильтрует разборы, оставляя только те, которые соответствуют лемме как нормальной форме,
        имеют наивысший score и принадлежат к одной и той же части речи.

        Args:
            lemma (str): исходная лемма.

        Returns:
            list[Parse]: список объектов разбора pymorphy3.

        Raises:
            ValueError: если разбор леммы не удался.
        """
        parses = self.morph.parse(lemma)
        if not parses:
            raise ValueError(f'разбор source не удался: {lemma}')

        # использование только тех разборов, где слово в нормальной форме.
        strict_cand = [p for p in parses if p.normal_form == lemma]
        # если строгие совпадения не найдены (слово "люди", а лемма "человек") - будут взяты все разборы
        cand = strict_cand if strict_cand else parses

        # сортировка по релевантности
        cand.sort(key=lambda p: p.score, reverse=True)

        # определение основной части речи
        best_pos = cand[0].tag.POS

        # 4. Возвращаем варианты с той же частью речи
        return [p for p in cand if p.tag.POS == best_pos]

    def get_target_forms(self, source_parse, target_lemma: str) -> list[str]:
        """
        находит целевые формы слова, соответствующие грамматическим признакам исходной формы.

        использует многоступенчатую фильтрацию разборов целевого слова по части речи,
        роду и категории (имя/фамилия/нарицательное), чтобы выбрать наиболее релевантную парадигму.
        затем выполняет инфлексию.

        Args:
            source_parse (Parse): объект разбора pymorphy3 для исходной формы.
            target_lemma (str): лемма целевого слова.

        Returns:
            list[str]: список сгенерированных форм целевого слова.

        Raises:
            RuntimeError: если целевая форма не может быть найдена через инфлексию.
        """
        # все варианты разбора целевого слова
        if target_lemma not in self._target_cache:
            self._target_cache[target_lemma] = self.morph.parse(target_lemma)

        all_target_parses = self._target_cache[target_lemma]

        src_tag = source_parse.tag
        src_pos = src_tag.POS

        # базовая фильтрация по части речи
        candidates = [p for p in all_target_parses if p.tag.POS == src_pos]
        if not candidates:
            # расширение поиска если ничего не найдено
            candidates = all_target_parses

        # фильтрация по роду (важно для фамилий/имен) для существительных и местоимений
        if src_pos in ('NOUN', 'NPRO') and src_tag.gender:
            gender_candidates = [p for p in candidates if p.tag.gender == src_tag.gender]
            if gender_candidates:
                candidates = gender_candidates

        # фильтрация по категории имя/фамилия/нарицательное
        src_is_surn = 'Surn' in src_tag
        src_is_name = 'Name' in src_tag
        src_is_common = not (src_is_surn or src_is_name)
        # поиск фамилий
        if src_is_surn:
            filtered = [p for p in candidates if 'Surn' in p.tag]
            if filtered: candidates = filtered
        # поиск имен
        elif src_is_name:
            filtered = [p for p in candidates if 'Name' in p.tag]
            if filtered: candidates = filtered
        # поиск нарицательных, избегая ФИ
        elif src_is_common:
            filtered = [p for p in candidates if 'Name' not in p.tag and 'Surn' not in p.tag]
            if filtered: candidates = filtered

        # выбор лучшего разбора из отфильтрованных
        best_p = max(candidates, key=lambda p: (len(p.lexeme), p.score))

        # индексация лексемы
        idx = {}
        for f in best_p.lexeme:
            k = self._make_form_key(f)
            idx.setdefault(k, []).append(f.word)
        for k in idx: idx[k] = sorted(set(idx[k]))

        # поиск по ключу
        key = self._make_form_key(source_parse)
        if key in idx:
            return idx[key]

        # фролбэк, инфлексия через pymorphy inflect
        required_grams = set()
        if src_tag.number: required_grams.add(src_tag.number)
        if src_tag.case: required_grams.add(src_tag.case)

        # род передается только для изменяемых по родам частей речи
        # для существительных/ФИ род уже выбран на этапе фильтрации best_p
        if src_pos in {'ADJF', 'ADJS', 'PRTF', 'PRTS', 'VERB', 'NPRO'}:
            if src_tag.gender: required_grams.add(src_tag.gender)

        if src_pos in {'VERB', 'INFN'}:
            if src_tag.tense: required_grams.add(src_tag.tense)
            if src_tag.person: required_grams.add(src_tag.person)
            if src_tag.mood: required_grams.add(src_tag.mood)

        if 'COMP' in src_tag.grammemes:
            required_grams.add('COMP')
        elif 'Supr' in src_tag.grammemes:
            required_grams.add('Supr')

        inf = best_p.inflect(required_grams)
        if inf:
            return [inf.word]

        # фролбэк: принудительная генерация для прилагательных
        if src_pos == 'ADJS':
            return [force_short_adj(target_lemma, src_tag.gender, src_tag.number)]
        if src_pos == 'COMP':
            return force_comp_adj(target_lemma, source_parse.word)

        # если вообще ничего нет (редкий случай для глаголов/причастий)
        raise RuntimeError(f'целевая форма не найдена: {target_lemma}')

    @staticmethod
    def _make_form_key(p) -> tuple:
        """
        создает сигнатуру грамматических признаков формы для сопоставления.

        Args:
            p (Parse): объект разбора pymorphy3.

        Returns:
            tuple: кортеж, содержащий ключевые грамматические признаки (POS, case, number, gender и т.д.).
        """
        t = p.tag
        pos = t.POS
        vm = tuple(sorted(get_v_markers(t)))

        # общие атрибуты
        case = getattr(t, 'case', None)
        num = getattr(t, 'number', None)
        gen = getattr(t, 'gender', None)
        anim = getattr(t, 'animacy', None)

        if pos in ('NOUN', 'NPRO', 'NUMR'):
            return pos, case, num, vm

        if pos in ('ADJF', 'ADJS'):
            deg = 'COMP' if 'COMP' in t.grammemes else ('Supr' if 'Supr' in t.grammemes else '')
            return pos, case, num, gen, deg, anim, vm

        # для глаголов важны: вид, время, наклонение, лицо, род (в прош. вр)
        if pos in ('VERB', 'INFN'):
            mood = getattr(t, 'mood', None)
            tense = getattr(t, 'tense', None)
            pers = getattr(t, 'person', None)
            voice = getattr(t, 'voice', None)  # иногда важно
            return pos, mood, tense, pers, num, gen, voice, vm

        if pos in ('PRTF', 'PRTS', 'GRND'):
            tense = getattr(t, 'tense', None)
            voice = getattr(t, 'voice', None)
            return pos, tense, voice, case, num, gen, anim, vm

        return pos, case, num, gen, vm  # дефолт

    def generate(self, source_lemma: str, target_lemma: str) -> dict | None:
        """
        генерирует все морфологические пары (source_form -> target_form)
        на основе лексем исходного и целевого слов.

        использует ручной склонятель (NounDecliner) для существительных,
        неизвестных словарю pymorphy3.

        Args:
            source_lemma (str): исходная лемма.
            target_lemma (str): целевая лемма.

        Returns:
            dict | None: словарь с метаданными и списком сгенерированных пар (FormRow),
                или None, если разбор исходной леммы не удался.
        """
        try:
            # получение списка всех подходящих парадигм
            src_parses = self.get_source_parses(source_lemma)
        except ValueError as e:
            print(f'ПРОПУСК: {source_lemma}: {e}')
            return None

        # тег первого разбора берется как основной для определения одушевленности и т.д.
        src_main_tag = src_parses[0].tag
        animate = 'anim' in src_main_tag.grammemes

        rows = []
        seen = set()

        # проверка есть ли целевое слово в pymorphy
        target_is_known = self.morph.word_is_known(target_lemma)

        # сборка единой лексемы из всех вариантов исходного слова
        full_lexeme = []
        seen_forms_tags = set()

        for p in src_parses:
            for f in p.lexeme:
                # одно слово может быть в разных падежах, уникальность определяется по паре (слово, тег)
                sig = (f.word, str(f.tag))
                if sig not in seen_forms_tags:
                    seen_forms_tags.add(sig)
                    full_lexeme.append(f)

        for sf in full_lexeme:
            pos = sf.tag.POS
            tag_str = str(sf.tag)
            target_words = []

            # ручная эвристика только для существительных не найденных в словаре
            use_manual_decliner = (pos == 'NOUN' and not target_is_known)

            if use_manual_decliner:
                case = getattr(sf.tag, 'case', None)
                number = getattr(sf.tag, 'number', None)
                if case and number:
                    try:
                        w = NounDecliner.decline(target_lemma, case, number, animate, sf.tag)
                        target_words = [w]
                    except Exception:  # noqa
                        pass

            if not target_words:
                try:
                    target_words = self.get_target_forms(sf, target_lemma)
                except Exception:  # noqa
                    target_words = [target_lemma]

            for tw in target_words:
                final_tgt = normalize_case_like(target_lemma, tw)
                key = (sf.word, final_tgt, tag_str)
                if key not in seen:
                    seen.add(key)
                    rows.append(FormRow(sf.word, final_tgt, tag_str))

        rows.sort(key=lambda r: (r.source, r.tag, r.target))

        return {
            'source_lemma': source_lemma,
            'target_lemma': target_lemma,
            'source_parse': str(src_main_tag),
            'forms': [
                {'source': r.source, 'target': r.target, 'tag': r.tag}
                for r in rows
            ]
        }


def normalize_case_like(reference: str, text: str) -> str:
    """
    приводит регистр строки `text` в соответствие с регистром строки `reference`.

    поддерживает капитализацию первого слова (для имен собственных) и
    обработку сложных слов через дефис (например, "Санкт-Петербург").

    Args:
        reference (str): строка-образец, регистр которой должен быть применен.
        text (str): строка, регистр которой нужно изменить.

    Returns:
        str: строка `text` с нормализованным регистром.
    """
    # если целевое слово в правилах написано с заглавной (Иванов, Санкт-Петербург)
    if reference and reference[0].isupper():
        # если это аббревиатура (СССР)
        if reference.isupper() and len(reference) > 1:
            return text.upper()
        # обработка дефисов (Санкт-Петербург -> Санкт-Петербурга)
        return "-".join(part.capitalize() for part in text.split("-"))

    # всё остальное в нижний регистр
    return text.lower()


def apply_orthography(stem: str, ending: str) -> str:
    """
    применяет правило русской орфографии: замена "ы" на "и" после шипящих и заднеязычных
    (г, к, х, ж, ч, ш, щ, ц).

    Args:
        stem (str): основа слова.
        ending (str): окончание слова.

    Returns:
        str: слово, собранное с учетом орфографических правил.
    """
    if not ending or not stem:
        return stem + ending

    first_char = ending[0]
    if first_char == 'ы' and stem[-1] in HUSH:
        return stem + 'и' + ending[1:]
    return stem + ending


def get_v_markers(tag) -> set[str]:
    """
    извлекает маркеры вариативности (V-tags) из морфологического тега pymorphy3.

    Args:
        tag (Tag): объект морфологического тега.

    Returns:
        set[str]: множество строк, начинающихся с 'V-'.
    """
    return {g for g in tag.grammemes if g.startswith('V-')}


def force_comp_adj(lemma: str, source_form: str | None = None) -> list[str]:
    """
    формирует сравнительную степень прилагательного, если pymorphy3 не смог это сделать.

    Args:
        lemma (str): лемма прилагательного.
        source_form (str | None, optional): форма исходного слова.
            используется для определения предпочтительного окончания ('ее' или 'ей').
            по умолчанию None.

    Returns:
        list[str]: список возможных форм сравнительной степени (обычно 'ее' и 'ей').
    """
    if not lemma.endswith(('ый', 'ой', 'ий')):
        # если лемма странная возврат как есть
        return [lemma]

    base = lemma[:-2]
    # если в source "ее", то и target "ее"
    if source_form:
        if source_form.endswith('ее'): return [base + 'ее']
        if source_form.endswith('ей'): return [base + 'ей']
    return [base + 'ее', base + 'ей']


def force_short_adj(lemma: str, gender: str | None, number: str) -> str:
    """
    формирует краткую форму прилагательного, если pymorphy3 не смог это сделать.

    Args:
        lemma (str): лемма прилагательного (должна оканчиваться на 'ый', 'ой' или 'ий').
        gender (str | None): требуемый род ('masc', 'femn', 'neut').
        number (str): требуемое число ('sing' или 'plur').

    Returns:
        str: сгенерированная краткая форма прилагательного.
    """
    if not lemma.endswith(('ый', 'ой', 'ий')):
        print(f'ВНИМАНИЕ: не удалось образовать краткую фому прилагательного из: {lemma}')
        return lemma
    base = lemma[:-2]
    ending_type = lemma[-2:]

    if number == 'plur':
        # ий -> и, ый -> ы (с учетом шипящих)
        return apply_orthography(base, 'и' if ending_type == 'ий' else 'ы')

    if gender == 'masc': return base
    if gender == 'femn': return base + 'а'
    if gender == 'neut': return base + ('е' if ending_type == 'ий' else 'о')

    return base


def get_exe_dir(compiled: bool = True) -> Path:
    """
    получает путь к директории, содержащей исполняемый файл или скрипт.

    Args:
        compiled (bool, optional): если True, предполагает, что скрипт скомпилирован
            (например, с помощью Nuitka) и использует `argv[0]`.
            иначе использует `__file__`. по умолчанию True.

    Returns:
        Path: объект пути к директории.
    """
    if compiled:
        return Path(argv[0]).resolve().parent
    return Path(__file__).parent.resolve()


def get_internal_data_dir() -> Path:
    """
    получает путь к директории, где предположительно находятся внутренние данные
    (например, при использовании Nuitka).

    Returns:
        Path: объект пути к директории скрипта.
    """
    return Path(__file__).resolve().parent


def fatal():
    """
    выводит сообщение о необходимости нажатия Enter для выхода и завершает программу с кодом 1.
    """
    input('нажми Enter, чтобы выйти...')
    exit(1)


def get_form_priority(tag) -> int:
    """
    определяет общий приоритет формы слова для разрешения коллизий в словаре замен.

    приоритет рассчитывается на основе падежа и числа (единственное число имеет бонус).

    Args:
        tag (Tag): объект морфологического тега pymorphy3.

    Returns:
        int: общий приоритет формы.
    """
    prio = 0  # базовый приоритет падежа
    tag_str = str(tag)
    for case, p in CASE_PRIORITY.items():
        if case in tag_str:
            prio = p
            break

    # повышает приоритет за единственное число (решает коллизию Тв.ед vs Дат.мн)
    if 'sing' in tag_str:
        prio += 20

    return prio


def main():
    """
    основная функция скрипта.

    обрабатывает входной YAML-файл с парами (source, target),
    генерирует все морфологические формы для каждой пары и сохраняет результаты
    в расширенный YAML-файл и плоский JSON-словарь замен.

    Raises:
        SystemExit: при ошибках чтения файлов, некорректном формате YAML или
            проблемах с инициализацией pymorphy3.
    """
    parser = ArgumentParser(description='русский морфологический генератор')
    parser.add_argument('input', nargs='?', help='путь к вводному YAML-файлу правил')
    args = parser.parse_args()

    base_dir = get_exe_dir(compiled=True)
    input_path = Path(args.input).resolve() if args.input else (base_dir / 'rules.yaml').resolve()

    if not input_path.exists():
        print(f'ОШИБКА: входной yaml-файл не найден: {input_path}')
        print(f'использование: {argv[0]} /path/to/rules.yaml')
        fatal()

    output_dir = input_path.parent
    output_yaml = output_dir / f'{input_path.stem}_output.yaml'
    output_json = output_dir / 'replacements.json'

    print(f'обработка: {input_path} ...')

    # загрузка правил
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            pairs = safe_load(f)
    except Exception as e:
        print(f'ОШИБКА при чтении YAML: {e}')
        print(f'пример YAML-файла:\n\n{EXAMPLE_YAML}\n')
        fatal()

    if not isinstance(pairs, list):
        print('ОШИБКА: корневой элемент YAML должен быть списком')
        print(f'пример YAML-файла:\n\n{EXAMPLE_YAML}\n')
        fatal()

    # инициалзация
    gen: PairGenerator | None = None
    try:
        gen = PairGenerator()
    except Exception as e:
        print(f'ОШИБКА инициализации: {e}')
        fatal()

    results = []

    # словарь для отслеживания приоритетов перезаписи: { word: priority_int }
    replacements_prio_map = {}

    for i, item in enumerate(pairs):
        s, t = item.get('source'), item.get('target')
        if not s or not t:
            continue

        s, t = s.strip(), t.strip()
        print(f'[{i + 1}/{len(pairs)}] {s} -> {t}...')

        # ключ в нижнем регистре -> значение с учетом регистра правила ("петров" -> "Иванов")
        s_lower = s.lower()
        t_aligned = normalize_case_like(t, t)

        if s_lower not in replacements_prio_map:
            replacements_prio_map[s_lower] = (t_aligned, 0)

        res = gen.generate(s, t)
        if res:
            results.append(res)
            for form in res['forms']:
                # ключи всегда в нижнем регистре
                src_word = form['source'].lower()
                # значения сохраняют регистр
                tgt_word = form['target']
                tag_str = form['tag']

                new_prio = get_form_priority(tag_str)

                if src_word not in replacements_prio_map:
                    replacements_prio_map[src_word] = (tgt_word, new_prio)
                else:
                    current_tgt, current_prio = replacements_prio_map[src_word]
                    if new_prio > current_prio:
                        replacements_prio_map[src_word] = (tgt_word, new_prio)
                    # TODO: если приоритеты равны - можно перезаписывать или оставлять старый

    # карта с приоритетами в плоский JSON
    replacements_flat = {k: v[0] for k, v in replacements_prio_map.items()}

    print(f'сохранение расширенных данных в: {output_yaml}')
    with open(output_yaml, 'w', encoding='utf-8') as f:
        safe_dump(results, f, allow_unicode=True, sort_keys=False, width=120)
    print(f'сохранение карты замен в: {output_json}')
    with open(output_json, 'w', encoding='utf-8') as f:
        dump(replacements_flat, f, ensure_ascii=False, indent=2, sort_keys=True)

    print('готово.')


if __name__ == '__main__':
    main()
