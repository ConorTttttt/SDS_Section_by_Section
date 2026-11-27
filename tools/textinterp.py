"""Shared text interpretation for every SDS rule.

Rules must not test raw keywords on their own. They ask this module whether the SDS *affirms* something,
whether a field is a "no data" statement, which sections it refers to, whether it says something in other
words, and whether a "such as" requirement is met. Unit tests: tests/test_textinterp.py.

  affirmed(text, pattern)    pattern occurs at least once without a negation in its clause
  negated_at(text, pos)      the clause before pos carries a negation cue
  is_no_data(value)          the value is (essentially) only a "no data / not available / not applicable" phrase
  has_reason(value)          a "no data" value gives a reason
  field_value(text, label)   value after a "label :" field, e.g. "Potential delayed effects : Not available"
  cross_refs(text)           section numbers referred to ("see Sections 7 and 8", "(see section 10.5)")
  refers_to(text, n)         text refers to section n (or one of its subsections)
  says(text, concept)        affirmed(text, SYNONYMS[concept])
  covers_examples(text, examples, generic=None)
                             a "such as" requirement: met when ANY example (or the generic wording) is affirmed
"""
import re

# ------------------------------------------------------------------ negation
NEG_CUE = re.compile(
    r"\b(?:no|not|never|none|nor|neither|without|cannot|can't|don't|doesn't|isn't|aren't|won't|"
    r"free (?:of|from)|absence of|exclud\w*|avoid\w*|prohibit\w*|instead of|rather than)\b|n't\b", re.I)
CLAUSE_BREAK = re.compile(r'[.;:!?\n]|\s[-–]\s|\bbut\b|\bhowever\b|\bexcept\b|\bunless\b', re.I)
NEG_WINDOW = 60  # characters of the clause before the match that are searched for a cue


def negated_at(text, pos):
    """True if the clause of `text` that ends at `pos` carries a negation cue close before it."""
    head = text[:pos]
    breaks = list(CLAUSE_BREAK.finditer(head))
    clause = head[breaks[-1].end():] if breaks else head
    return bool(NEG_CUE.search(clause[-NEG_WINDOW:]))


def affirmed(text, pattern, flags=re.I):
    """True if `pattern` occurs at least once in `text` outside a negated clause."""
    text = text or ''
    for m in re.finditer(pattern, text, flags):
        if not negated_at(text, m.start()):
            return True
    return False


def affirmed_matches(text, pattern, flags=re.I):
    text = text or ''
    return [m for m in re.finditer(pattern, text, flags) if not negated_at(text, m.start())]


# ------------------------------------------------------------------ "no data" statements
NO_DATA = (r"no (?:further |additional |specific |relevant |other |test |known )*(?:data|information|test data)(?: (?:is|are))?(?: available)?(?: for this product)?"
           r"|(?:data|information) (?:is |are )?not available|not (?:available|determined|known|established|tested|specified)"
           r"|no data available|n/?a|n\.?d\.?|unknown|undetermined|none known|nothing specified|-+")
NOT_APPLICABLE = r"not applicable|not relevant|does not apply"
REASON = (r"because|due to|since|as (?:the|this|it)|based on|not relevant|not tested|criteria (?:are|is) not met|"
          r"classification criteria|considered|expected|for (?:this|the) product|the (?:product|substance|mixture) (?:is|does|has|contains)|"
          r"is not (?:reactive|flammable|classified)|no reactive|not classified|under normal conditions")
_FILLER = r"[\s.,;:()\-–/]*"


_ABOUT = set('related regarding concerning about to on for of with in this the its any or and product mixture substance '
             'ingredients ingredient components reactivity stability available data information test specific yet currently present '
             'further additional relevant other known'.split())


HAZARD_WORDS = r'react|explo|flamm|toxic|corros|decompos|ignit|incompatib|avoid|water|acid|alkal|oxidi|heat|polymer|peroxide|gas'


def is_no_data(value):
    """True if the value says only that no data/information is available or that the item is not applicable.
    A no-data phrase followed by a few words that add no hazard information still counts
    ("No data available: synthetic fixture"); one followed by a real statement does not
    ("Not available. Reacts violently with water")."""
    v = ' '.join((value or '').split()).lower()
    if not v or not re.search(r'\b(?:' + NO_DATA + '|' + NOT_APPLICABLE + r')\b', v):
        return v.strip(' .:-–') == '' and bool(v)
    rest = re.sub(r'\b(?:' + NO_DATA + '|' + NOT_APPLICABLE + r')\b', ' ', v)
    words = [w for w in re.findall(r"[a-z]+", rest) if w not in _ABOUT]
    if not words:
        return True
    starts = re.match(r'\W*(?:' + NO_DATA + '|' + NOT_APPLICABLE + r')\b', v)
    return bool(starts) and len(words) <= 3 and not re.search(HAZARD_WORDS, rest)


def has_reason(value):
    return bool(re.search(REASON, (value or '').lower()))


def field_value(text, label, maxlen=200):
    """Value printed after a 'label :' field (two-column SDS layouts), up to the end of its sentence or the next
    'Label :' field. Returns None if the label is absent."""
    m = re.search(label + r'\s*:?\s*(.{0,%d}?)(?:\.(?=\s|$)|(?=\s+[A-Z][\w /()-]{2,40}\s*:)|\n|$)' % maxlen, text or '', re.I)
    return m.group(1).strip() if m else None


# ------------------------------------------------------------------ cross-references
_SEC_LIST = r'(\d{1,2}(?:\.\d{1,2})?(?:\s*(?:,|and|&|/|or)\s*\d{1,2}(?:\.\d{1,2})?)*)'
XREF = re.compile(r'(?:see|refer(?:ence)? to|as (?:described|detailed|specified|given|listed) in|according to|in accordance with|per|cf\.?|'
                  r'information (?:in|on)|given in|described in|listed in|under)\s+(?:the\s+)?(?:information (?:in|of)\s+)?'
                  r'(?:sub)?sections?\s*(?:no\.?\s*)?' + _SEC_LIST, re.I)
XREF_BARE = re.compile(r'\((?:see\s+)?(?:sub)?sections?\s+' + _SEC_LIST + r'\)', re.I)


def cross_refs(text):
    out = set()
    for rx in (XREF, XREF_BARE):
        for m in rx.finditer(text or ''):
            for n in re.findall(r'\d{1,2}(?:\.\d{1,2})?', m.group(1)):
                out.add(n)
    return out


def refers_to(text, section):
    """True if text refers to `section` ('8') or one of its subsections ('8.2'); '10.5' also matches a reference to '10'."""
    section = str(section)
    for n in cross_refs(text):
        if n == section or n.startswith(section + '.') or section.startswith(n + '.'):
            return True
    return False


# ------------------------------------------------------------------ synonyms
SYNONYMS = {
    # first aid
    'rinse_water': r'rins\w*|flush\w*|irrigat\w*|wash\w*|hose\w*|shower\w*|douse|bathe',
    'rinse_eyes': r'(?:rins|flush|irrigat|wash|bath)\w* (?:\w+ ){0,6}eyes?|eyes? (?:\w+ ){0,4}(?:rins|flush|irrigat|wash)\w*|eye ?wash|(?:rins|flush|irrigat)\w*',
    'medical': r'medical (?:attention|advice|help|treatment|assistance|care)|physician|doctor|poison (?:cent(?:er|re)|control|information)|hospital|emergency (?:medical|department)',
    'urgent': r'immediate\w*|urgent\w*|at once|without delay|straight away|as soon as possible',
    'remove_clothing': r'(?:remove|take off|strip off|tak\w* off|remov\w*)\s+(?:\w+\s+){0,4}(?:cloth\w*|garments?|shoes|footwear)',
    'wash_clothing': r'wash\w* (?:\w+ ){0,6}(?:before re-?use|before wearing again)|(?:cloth\w*|garments?) (?:\w+ ){0,4}(?:wash\w*|launder\w*) before',
    'fresh_air': r'fresh air|remove (?:\w+ ){0,4}from (?:the )?(?:exposure|area|source|contaminated)|remove from exposure|terminate (?:the )?exposure|move (?:\w+ ){0,3}(?:to|into) (?:fresh|open) air',
    'no_vomit': r"(?:do not|don't|never|not to|must not|should not)\s+induce vomiting|no induced vomiting",
    'induce_vomit': r'induce vomiting|cause vomiting|make (?:\w+ ){0,2}vomit',
    'rinse_mouth': r'rins\w* (?:\w+ ){0,3}mouth|clean (?:the )?mouth|mouth (?:\w+ ){0,3}(?:with )?water|wash\w* (?:\w+ ){0,3}mouth',
    'contact_lenses': r'contact lens\w*',
    'firstaider_ppe': r'first[- ]?aiders?|rescuers?|responders?|own safety|protect yourself|self[- ]protection|pocket mask|mouth-to-mouth',
    # firefighting
    'firefighting': r'fire-?fighters?|fire[- ]fighting|fire brigade|fire service',
    'firefighter_ppe': r'breathing apparatus|scba|self[- ]contained|respirat\w*|protective (?:gear|clothing|equipment|suit)|en ?469|turn-?out gear|full protective',
    # handling / hygiene
    'no_eat_drink_smoke': r'(?:eat|drink|smok)\w*',
    'wash_hands': r'wash\w* (?:\w+ ){0,3}hands|hands (?:\w+ ){0,3}(?:wash|clean)\w*|hand ?wash\w*|personal hygiene',
    'hygiene_generic': r'(?:good )?(?:industrial|occupational|personal|general) hygiene|hygiene (?:measures|practices?|advice)',
    'ventilation': r'ventilat\w*|exhaust|fume (?:hood|cupboard)|extraction|outdoors',
    'ignition': r'ignition|sparks?|open flames?|naked flames?|hot surfaces?|smoking',
    # spills
    'contain_spill': r'dike|dyke|bund\w*|contain\w*|cover (?:the )?drains|prevent (?:further )?(?:spread|leak\w*)|absorb\w*|soak\w* up|\bdam\b|stop (?:the )?leak',
    'clean_spill': r'collect\w*|sweep\w*|soak\w* up|absorb\w*|shovel\w*|vacuum\w*|pick\w* up|clean\w* up|mop\w* up|wipe\w* up|scoop\w*',
    # symptoms
    'eye_symptoms': r'eye damage|blind\w*|burn\w*|pain\w*|water\w*|redness|tear\w*|lacrimat\w*|irritat\w*|blurred',
}


def says(text, concept):
    return affirmed(text, SYNONYMS[concept])


# ------------------------------------------------------------------ "such as" requirements
def covers_examples(text, examples, generic=None):
    """Annex II 'such as' lists are examples, not a checklist: the requirement is met if any example (or the
    generic wording) is present. The examples are often prohibitions ("do not eat, drink or smoke"), so presence is
    tested without the negation filter. Returns (met, examples_not_mentioned)."""
    hit = {name for name, rx in examples.items() if re.search(rx, text or '', re.I)}
    met = bool(hit) or bool(generic and re.search(generic, text or '', re.I))
    return met, [n for n in examples if n not in hit]
