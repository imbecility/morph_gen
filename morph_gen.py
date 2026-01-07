from argparse import ArgumentParser
from dataclasses import dataclass
from json import dump
from pathlib import Path
from sys import exit, argv, stderr

from pymorphy3 import MorphAnalyzer
from yaml import safe_load, safe_dump


@dataclass(frozen=True)
class FormRow:
    source: str
    target: str
    tag: str


HUSH = set('гкхжчшщц')

SCHEMAS = {
    'masc_cons': {
        'sing': {'nomn': '', 'gent': 'а', 'datv': 'у', 'accs': None, 'ablt': 'ом', 'loct': 'е'},
        'plur': {'nomn': 'ы', 'gent': 'ов', 'datv': 'ам', 'accs': None, 'ablt': 'ами', 'loct': 'ах'}
    },
    'masc_soft': {
        'sing': {'nomn': '', 'gent': 'я', 'datv': 'ю', 'accs': None, 'ablt': 'ем', 'loct': 'е'},
        'plur': {'nomn': 'и', 'gent': 'ей', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
    'fem_a': {
        'sing': {'nomn': 'а', 'gent': 'ы', 'datv': 'е', 'accs': 'у', 'ablt': 'ой', 'loct': 'е'},
        'plur': {'nomn': 'ы', 'gent': '', 'datv': 'ам', 'accs': None, 'ablt': 'ами', 'loct': 'ах'}
    },
    'fem_ya': {
        'sing': {'nomn': 'я', 'gent': 'и', 'datv': 'е', 'accs': 'ю', 'ablt': 'ей', 'loct': 'е'},
        'plur': {'nomn': 'и', 'gent': '', 'datv': 'ам', 'accs': None, 'ablt': 'ами', 'loct': 'ах'}
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
    'fem_soft': {
        'sing': {'nomn': 'ь', 'gent': 'и', 'datv': 'и', 'accs': 'ь', 'ablt': 'ью', 'loct': 'и'},
        'plur': {'nomn': 'и', 'gent': 'ей', 'datv': 'ям', 'accs': None, 'ablt': 'ями', 'loct': 'ях'}
    },
}


class NounDecliner:
    """
    принудительно склоняет существительные по заданным схемам,
    игнорируя словарь pymorphy для target-слова.

    - схемы окончаний: (Singular, Plural)
    - ключи: (nomn, gent, datv, accs, ablt, loct)
    - None в accs означает "вычисляется динамически по одушевленности"
    """
    @staticmethod
    def classify(word: str) -> tuple[str, str]:
        # базовая эвристика
        if word.endswith(('у', 'ю', 'э', 'о', 'е', 'и')):
            # слово считается склоняемым если оканчивается на гласную, даже если не попадает в стандартные паттерны
            if word.endswith(('у', 'э')):
                return 'indeclinable', word
            if word.endswith('и') and not word.endswith('ии'):
                return 'indeclinable', word

        # стандартные окончания
        if word.endswith('ия'): return 'fem_ia', word[:-2]
        if word.endswith('ие'): return 'neut_ie', word[:-2]

        # беглые гласные (эвристика для окончаний -ок)
        # односложные (рок, ток, сок) не теряют гласную и будут исключены
        if word.endswith('ок') and len(word) > 3 and word[-3] not in 'аяуюиыеёо':
            # TODO: сделать отдельный флаг или доп. логику
            pass

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
            if word.endswith(('ость', 'есть', 'знь', 'дь')):  # тетрадь, жизнь
                return 'fem_soft', stem
            # ь
            return 'masc_soft', stem

        # согласная
        return 'masc_cons', word

    @classmethod
    def decline(cls, lemma: str, case: str, number: str, animate: bool, src_tag=None) -> str:
        # нормализация падежей через pymorphy
        case_map = {'gen2': 'gent', 'loc2': 'loct', 'voct': 'nomn'}
        case = case_map.get(case, case)

        decl_type, stem = cls.classify(lemma)

        if decl_type not in SCHEMAS:
            raise RuntimeError(f'тип склонения для {lemma} неизвестен')

        schema = SCHEMAS[decl_type].get(number)
        if not schema:
            raise RuntimeError(f'номер "{number}" не поддерживается для типа "{decl_type}"')

        # базовое окончание
        ending = schema.get(case)

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
    def __init__(self):
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
            except Exception:
                print(f'[ОШИБКА] словари нигде не найдены!', file=stderr)
                exit(1)

        self._target_cache = {}

    def get_source_lexeme(self, lemma: str):
        parses = self.morph.parse(lemma)
        if not parses:
            raise ValueError(f'разбор source не удался: {lemma}')
        # лучший разбор, совпадающий с леммой
        cand = [p for p in parses if p.normal_form == lemma] or parses
        cand.sort(key=lambda p: p.score, reverse=True)
        return list(cand[0].lexeme), cand[0].tag

    def get_target_forms(self, source_parse, target_lemma: str) -> list[str]:
        """
        пытается найти форму target через pymorphy,
        если это краткое/полное прилагательное и pymorphy не знает, строит принудительно.
        """
        # кэшированная база target
        if target_lemma not in self._target_cache:
            all_p = self.morph.parse(target_lemma)
            # поиск разбора с максимальным кол-вом форм в парадигме
            best_p = max(all_p, key=lambda p: (len(p.lexeme), p.score))

            # индексация лексемы
            idx = {}
            for f in best_p.lexeme:
                k = self._make_form_key(f)
                idx.setdefault(k, []).append(f.word)
            for k in idx: idx[k] = sorted(set(idx[k]))

            self._target_cache[target_lemma] = (best_p, idx)

        tp, idx = self._target_cache[target_lemma]

        # поиск по ключу
        key = self._make_form_key(source_parse)
        if key in idx:
            return idx[key]

        # фролбэк через pymorphy inflect
        grams = set(source_parse.tag.grammemes) - {g for g in source_parse.tag.grammemes if g.startswith('V-')}
        inf = tp.inflect(grams)
        if inf:
            return [inf.word]

        # фролбэк: принудительная генерация для прилагательных
        pos = source_parse.tag.POS
        if pos == 'ADJS':
            return [force_short_adj(target_lemma, source_parse.tag.gender, source_parse.tag.number)]
        if pos == 'COMP':
            return force_comp_adj(target_lemma, source_parse.word)

        # если вообще ничего нет (редкий случай для глаголов/причастий)
        # TODO: вместо падения можно вернуть лемму или сделать эвристику
        raise RuntimeError(f'целевая форма не найдена: {target_lemma} для тега {source_parse.tag}')

    @staticmethod
    def _make_form_key(p) -> tuple:
        """
        создает сигнатуру формы для сопоставления
        """
        t = p.tag
        pos = t.POS
        vm = tuple(sorted(get_v_markers(t)))

        # общие атрибуты
        case = getattr(t, "case", None)
        num = getattr(t, "number", None)
        gen = getattr(t, "gender", None)
        anim = getattr(t, "animacy", None)

        if pos in ('NOUN', 'NPRO', 'NUMR'):
            return pos, case, num, vm

        if pos in ('ADJF', 'ADJS'):
            deg = 'COMP' if 'COMP' in t.grammemes else ('Supr' if 'Supr' in t.grammemes else '')
            return pos, case, num, gen, deg, anim, vm

        # для глаголов важны: вид, время, наклонение, лицо, род (в прош. вр)
        if pos in ('VERB', 'INFN'):
            mood = getattr(t, "mood", None)
            tense = getattr(t, "tense", None)
            pers = getattr(t, "person", None)
            voice = getattr(t, "voice", None)  # иногда важно
            return pos, mood, tense, pers, num, gen, voice, vm

        if pos in ('PRTF', 'PRTS', 'GRND'):
            tense = getattr(t, "tense", None)
            voice = getattr(t, "voice", None)
            return pos, tense, voice, case, num, gen, anim, vm

        return pos, case, num, gen, vm  # дефолт

    def generate(self, source_lemma: str, target_lemma: str) -> dict:
        lexeme, src_main_tag = self.get_source_lexeme(source_lemma)
        animate = 'anim' in src_main_tag.grammemes

        rows = []
        seen = set()

        for sf in lexeme:
            pos = sf.tag.POS
            tag_str = str(sf.tag)

            target_words = []

            if pos == 'NOUN':
                # принудительная стратегия для существительных
                case = getattr(sf.tag, 'case', None)
                number = getattr(sf.tag, 'number', None)
                if case and number:
                    w = NounDecliner.decline(target_lemma, case, number, animate, sf.tag)
                    target_words = [w]
            else:
                # остальные через pymorphy
                target_words = self.get_target_forms(sf, target_lemma)

            for tw in target_words:
                final_tgt = normalize_case_like(sf.word, tw)
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


def normalize_case_like(src: str, dst: str) -> str:
    """
    сохраняет регистр как в исходнике
    """
    if src.isupper():
        return dst.upper()
    if src.istitle():
        return dst.capitalize()
    return dst


def apply_orthography(stem: str, ending: str) -> str:
    """
    применяет правило: "ы" -> "и" после г, к, х, ж, ч, ш, щ, ц.
    """
    if not ending or not stem:
        return stem + ending

    first_char = ending[0]
    if first_char == 'ы' and stem[-1] in HUSH:
        return stem + 'и' + ending[1:]
    return stem + ending


def get_v_markers(tag) -> set[str]:
    return {g for g in tag.grammemes if g.startswith('V-')}


def force_comp_adj(lemma: str, source_form: str | None = None) -> list[str]:
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
    if not lemma.endswith(('ый', 'ой', 'ий')):
        raise RuntimeError(f'не удалось образовать краткую фому прилагательного из: {lemma}')

    base = lemma[:-2]
    ending_type = lemma[-2:]

    if number == 'plur':
        # ий -> и, ый -> ы (с учетом шипящих)
        return apply_orthography(base, 'и' if ending_type == 'ий' else 'ы')

    if gender == 'masc': return base
    if gender == 'femn': return base + 'а'
    if gender == 'neut': return base + ('е' if ending_type == 'ий' else 'о')

    return base


def load_pairs(path: str) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        data = safe_load(f)
    return data if isinstance(data, list) else []


def get_exe_dir(compiled: bool = True) -> Path:
    if compiled:
        return Path(argv[0]).resolve().parent
    return Path(__file__).parent.resolve()


def get_internal_data_dir() -> Path:
    return Path(__file__).resolve().parent


def fatal():
    input('нажми Enter, чтобы выйти...')
    exit(1)


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

def main():
    parser = ArgumentParser(description='русский морфологический генератор')
    parser.add_argument('input', nargs='?', help='путь к вводному YAML-файлу правил')
    args = parser.parse_args()

    base_dir = get_exe_dir(compiled=True)
    input_path = Path(args.input).resolve() if args.input else (base_dir / 'rules.yaml').resolve()

    if not input_path.exists():
        print(f'ОШИБКА: входной yaml-файл не найден: {input_path}')
        print(f'использование: {argv[0]} /path/to/rules.yaml]')
        print(f'пример YAML-файла:\n\n{EXAMPLE_YAML}\n')
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
    try:
        gen = PairGenerator()
    except Exception as e:
        print(f'ОШИБКА инициализации: {e}')
        fatal()

    results = []
    replacements_flat = {}

    for i, item in enumerate(pairs):
        s, t = item.get('source'), item.get('target')
        if not s or not t:
            continue

        s, t = s.strip(), t.strip()
        print(f'[{i + 1}/{len(pairs)}] {s} -> {t}...')

        res = gen.generate(s, t)
        if res:
            results.append(res)
            for form in res['forms']:
                src_word = form['source']
                tgt_word = form['target']
                # перезапись существующих ключей
                # TODO: проверка а коллизии
                replacements_flat[src_word] = tgt_word

    print(f'сохранение расширенных данных в: {output_yaml}')
    with open(output_yaml, 'w', encoding='utf-8') as f:
        safe_dump(results, f, allow_unicode=True, sort_keys=False, width=120)
    print(f'сохранение карты замен в: {output_json}')
    with open(output_json, 'w', encoding='utf-8') as f:
        dump(replacements_flat, f, ensure_ascii=False, indent=2, sort_keys=True)

    print('готово.')


if __name__ == '__main__':
    main()
