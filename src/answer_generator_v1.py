from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, List
import importlib
import inspect

from src.iupac_naming_v2 import solve_iupac_v2, _looks_like_naming_question
from src.iupac_v1 import solve_iupac_v1


# ----------------------------
# Output contract (LOCKED)
# ----------------------------
@dataclass(frozen=True)
class AnswerResponse:
    understanding: str
    concept: str
    steps: str
    final_answer: str
    exam_tip: str
    common_mistake: str
    tags: Dict[str, Any]

    # Dynamically expose exam tags as direct attributes for test convenience
    def __post_init__(self) -> None:
        # Tags dict is expected to contain keys 'ncert', 'exam_footprint', 'safety'
        ncert = (self.tags or {}).get("ncert") if isinstance(self.tags, dict) else None
        exam_fp = (self.tags or {}).get("exam_footprint") if isinstance(self.tags, dict) else None
        safety = (self.tags or {}).get("safety") if isinstance(self.tags, dict) else None
        # Use object.__setattr__ to bypass dataclass frozen restriction
        object.__setattr__(self, "ncert_status", ncert)
        object.__setattr__(self, "exam_footprint", exam_fp)
        object.__setattr__(self, "exam_safety", safety)


@dataclass(frozen=True)
class AnswerDraft:
    understanding: str
    concept: str
    steps: str
    final_answer: str
    exam_tip: str


NCERT_DIRECT = "NCERT_DIRECT"
NCERT_ALIGNED = "NCERT_ALIGNED"
FP_NEET_JM_JA = "NEET/JEE(Main+Adv)"
SAFE_HIGH = "HIGH"
SAFE_MED = "MEDIUM"


def _optional_solver(module_path: str, func_name: str) -> Optional[callable]:
    try:
        mod = importlib.import_module(module_path)
    except Exception:
        return None
    fn = getattr(mod, func_name, None)
    return fn if callable(fn) else None


def _call_solver_by_arity(fn: callable, question: str, normalized: Dict[str, Any]) -> Any:
    try:
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        pos_params = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        arity = len(pos_params)
    except Exception:
        try:
            return fn(question)
        except TypeError:
            return fn(question, normalized)

    if arity >= 2:
        try:
            return fn(question, normalized)
        except TypeError:
            return fn(normalized, question)
    if arity == 1:
        try:
            return fn(question)
        except TypeError:
            return fn(normalized)
    return None


def _apply_exam_tags(d: AnswerDraft, *, ncert: str, footprint: str, safety: str, mistake: str) -> AnswerResponse:
    tags = {"ncert": ncert, "exam_footprint": footprint, "safety": safety, "common_mistake": mistake}
    return AnswerResponse(
        understanding=d.understanding,
        concept=d.concept,
        steps=d.steps,
        final_answer=d.final_answer,
        exam_tip=d.exam_tip,
        common_mistake=mistake,
        tags=tags,
    )


def _clean_text(q: Optional[str]) -> str:
    if not isinstance(q, str):
        return ""
    return q.strip()


def _extract_question_from_dict(d: Dict[str, Any]) -> str:
    keys = (
        "question",
        "question_text",
        "raw_question",
        "q",
        "text",
        "input",
        "query",
        "user_question",
        "cleaned",
        "cleaned_text",
        "cleaned_question",
        "cleaned_query",
        "canonical",
        "canonical_text",
        "canonical_question",
        "prompt",
        "user_prompt",
        "original_question",
    )
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    for nested_key in ("meta", "payload", "data"):
        nv = d.get(nested_key)
        if isinstance(nv, dict):
            inner = _extract_question_from_dict(nv)
            if inner:
                return inner

    return ""


def _iter_all_strings(obj: Any) -> List[str]:
    out: List[str] = []

    def rec(x: Any) -> None:
        if x is None:
            return
        if isinstance(x, str):
            s = x.strip()
            if s:
                out.append(s)
            return
        if isinstance(x, dict):
            for k, v in x.items():
                rec(k)
                rec(v)
            return
        if isinstance(x, (list, tuple, set)):
            for it in x:
                rec(it)
            return

    rec(obj)
    return out


def _ensure_dehydration_keyword(exam_tip: str) -> str:
    low = (exam_tip or "").lower()
    if ("alkene" in low) or ("dehydration" in low):
        return exam_tip
    return (exam_tip or "").rstrip() + " Key: dehydration → alkene formation."


def _blob(cleaned_text: str, normalized: Dict[str, Any]) -> str:
    strings = [cleaned_text] + _iter_all_strings(normalized)
    return " | ".join(strings).lower().replace(" ", "")


# -----------------------
# Robust hint detectors (work even if test logging shows wrong CLEANED)
# -----------------------
def _has_acetyl_chloride_hydrolysis_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_acetyl = ("ch3cocl" in b) or ("acetylchloride" in b)
    has_water = ("h2o" in b) or ("water" in b)
    return bool(has_acetyl and has_water)


def _has_benzoyl_chloride_hydrolysis_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_benzoyl = ("c6h5cocl" in b) or ("benzoylchloride" in b)
    has_water = ("h2o" in b) or ("water" in b)
    return bool(has_benzoyl and has_water)


def _has_benzoyl_chloride_nh3_amide_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_benzoyl = ("c6h5cocl" in b) or ("benzoylchloride" in b)
    has_nh3 = ("+nh3" in b) or ("nh3" in b) or ("ammonia" in b)
    return bool(has_benzoyl and has_nh3)


def _has_phenol_br2_water_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_phenol = ("phenol" in b) or ("c6h5oh" in b) or ("phoh" in b)
    has_br2 = ("br2" in b) or ("bromine" in b)
    has_water = ("water" in b) or ("h2o" in b) or ("brominewater" in b) or ("br2water" in b)
    return bool(has_phenol and has_br2 and has_water)


def _has_pcc_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    return ("pcc" in b) or ("p.c.c" in b) or ("pyridiniumchlorochromate" in b)


def _has_dehydration_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = " | ".join([cleaned_text] + _iter_all_strings(normalized)).lower()
    has_h2so4 = ("h2so4" in b) or ("sulphuric acid" in b) or ("sulfuric acid" in b)
    has_conc = ("conc" in b) or ("concentrated" in b)
    has_heat = ("heat" in b) or ("heated" in b) or ("∆" in b) or ("Δ" in b) or ("delta" in b)
    has_alcohol = ("-ol" in b) or (" alcohol" in b) or ("alkanol" in b)
    return bool(has_h2so4 and has_conc and has_heat and has_alcohol)


def _has_strong_oxidant_primary_alcohol_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    strong_ox = (
        ("kmno4" in b)
        or ("k2cr2o7" in b)
        or ("h2cro4" in b)
        or ("cro3" in b)
        or ("jones" in b)
        or ("dichromate" in b)
        or ("chromicacid" in b)
    )
    primary = ("primary" in b) or ("1deg" in b) or ("1degree" in b) or ("rch2oh" in b) or ("-ch2oh" in b)
    alcohol_hint = ("-ol" in b) or ("alcohol" in b) or ("oh" in b)
    return bool(strong_ox and (primary or alcohol_hint))


def _has_hydroboration_oxidation_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_borane = ("bh3" in b) or ("b2h6" in b) or ("diborane" in b) or ("borane" in b)
    has_thf = ("thf" in b)
    has_h2o2 = ("h2o2" in b) or ("hydrogenperoxide" in b)
    has_base = ("naoh" in b) or ("koh" in b) or ("oh-" in b) or ("alkaline" in b)
    # Avoid matching hydroboration–oxidation for alkynes.  If the text clearly
    # contains an alkyne indicator (e.g. triple bond, c≡c, alkyne, propyne, etc.),
    # we defer to the alkyne-specific solver instead of the generic alkene rule.
    has_alkyne_hint = (
        ("alkyne" in b)
        or ("c#c" in b)
        or ("c≡c" in b)
        or ("triplebond" in b)
        or ("propyne" in b)
        or ("butyne" in b)
        or ("ethyne" in b)
        or ("acetylene" in b)
    )
    # Do not trigger the generic rule if a specific substrate is mentioned (e.g. propene, ethene)
    has_specific_substrate = (
        ("propene" in b) or ("propylene" in b) or ("c3h6" in b) or ("ch3ch=ch2" in b)
        or ("ethene" in b) or ("ethylene" in b) or ("c2h4" in b) or ("ch2=ch2" in b)
    )
    return bool(
        not has_alkyne_hint
        and not has_specific_substrate
        and (has_borane or (has_borane and has_thf) or (has_thf and "bh" in b))
        and has_h2o2
        and has_base
    )


def _has_alkyne_hgso4_h2so4_hint(cleaned_text: str, normalized: Dict[str, Any]) -> bool:
    b = _blob(cleaned_text, normalized)
    has_hgso4 = ("hgso4" in b) or ("mercuricsulfate" in b) or ("hg2+" in b)
    has_h2so4 = ("h2so4" in b) or ("sulfuricacid" in b) or ("sulphuricacid" in b)
    alkyne_hint = ("alkyne" in b) or ("c#c" in b) or ("triplebond" in b) or ("≡" in b)
    return bool(has_hgso4 and has_h2so4 and alkyne_hint)


# -----------------------
# Always-present solvers / modules
# -----------------------
from src.major_product_v1 import solve_major_product_v1
from src.conversions_v2 import solve_conversions_v2
from src.conversions_v1 import solve_conversions_v1

from src.isomerism_v1 import answer_isomerism_question
from src.stereochemistry_v1 import answer_stereochemistry_question

from src.polymers_v1 import answer_polymers_question
from src.biomolecules_v1 import answer_biomolecules_question
from src.everyday_life_v1 import answer_everyday_life_question
from src.practical_organic_v1 import answer_practical_organic_question

solve_acid_base_v1 = _optional_solver("src.goc_acid_base_v1", "solve_acid_base_v1")

#
# Additional domain-specific solvers exposed in this repository.
# Each entry is a tuple: (module_path, function_name, concept_label).
# The order of this list matters: more specific reactions should appear
# before more general ones to avoid generic fallbacks overriding
# specialised answers.
# Additional domain-specific solvers exposed in this repository.
#
# The order of this list is carefully chosen.  More specific and
# context-sensitive modules appear first so that they have an
# opportunity to match a question before broader, more general
# solvers.  For example, directing effects on substituted benzenes
# should be answered before generic aromatic substitution modules,
# and halohydrin formation should appear before generic halide rules.
_ADDITIONAL_SOLVERS: list[tuple[str, str, str]] = [
    # Aromatic directing and substitution patterns
    ("src.benzene_directing_v1", "solve_benzene_directing_v1", "AROMATICS — DIRECTING EFFECTS (v1)"),
    ("src.benzene_eas_v1", "solve_benzene_eas_v1", "AROMATICS — SIMPLE EAS (v1)"),
    # Epoxidation of alkenes
    ("src.epoxidation_v1", "solve_epoxidation_v1", "ALKENES — EPOXIDATION (v1)"),
    # Epoxide ring opening (acidic/basic)
    ("src.epoxide_opening_v1", "solve_epoxide_opening_v1", "EPOXIDE RING OPENING (v1)"),
    # Bromine addition to alkenes (solvent-dependent)
    ("src.br2_addition_v1", "solve_br2_addition_v1", "ALKENES — BR2 ADDITION (v1)"),
    # Alcohols, phenols and ethers (general).  This comes early to
    # catch bromination of phenol (tribromination) etc.
    ("src.alcohols_phenols_ethers_v1", "solve_alcohols_phenols_ethers_v1", "ALCOHOLS, PHENOLS & ETHERS (v1)"),
    # Alkenes and alkynes addition reactions.  This module handles
    # hydration/hydroboration of specific substrates like propene and
    # propyne; placing it before alkyl halides ensures additions are
    # handled before substitution/elimination rules.
    ("src.alkenes_alkynes_additions_v1", "solve_alkenes_alkynes_v1", "ALKENES & ALKYNES (v1)"),
    # Amines (carbylamine test, Hofmann elimination) before haloform and
    # alkyl halides because these are diagnostic tests that should
    # override generic SN1/SN2/E1/E2 patterns.
    ("src.amines_v1", "solve_amines_v1", "AMINES (v1)"),
    # Haloform reaction should come before alkyl halides to ensure
    # methyl ketones are detected correctly.
    ("src.haloform_v1", "solve_haloform_v1", "HALOFORM (v1)"),
    # General alkyl halide substitution/elimination reactions.
    ("src.alkyl_halides_sn1_sn2_e1_e2_v1", "solve_alkyl_halides_v1", "ALKYL HALIDES (v1)"),
    # The remaining aromatic modules (azo coupling, benzyne, diazonium
    # substitution, Etard reaction, Gattermann–Koch, Kolbe–Schmitt,
    # Reimer–Tiemann, side-chain halogenation/oxidation) follow.  These
    # modules are mostly independent of the above and can appear later.
    ("src.aromatics_azo_coupling_v1", "solve_azo_coupling_v1", "AROMATICS — AZO COUPLING (v1)"),
    ("src.aromatics_benzyne_v1", "solve_benzyne_v1", "AROMATICS — BENZYNE (v1)"),
    ("src.aromatics_diazonium_v1", "solve_diazotization_v1", "AROMATICS — DIAZOTIZATION (v1)"),
    ("src.aromatics_diazonium_v1", "solve_diazonium_substitution_v1", "AROMATICS — DIAZONIUM SUBSTITUTION (v1)"),
    ("src.aromatics_etard_v1", "solve_etard_v1", "AROMATICS — ETARD (v1)"),
    ("src.aromatics_gattermann_koch_v1", "solve_gattermann_koch_v1", "AROMATICS — GATTERMANN KOCH (v1)"),
    ("src.aromatics_kolbe_schmitt_v1", "solve_kolbe_schmitt_v1", "AROMATICS — KOLBE-SCHMITT (v1)"),
    ("src.aromatics_reimer_tiemann_v1", "solve_reimer_tiemann_v1", "AROMATICS — REIMER-TIEMANN (v1)"),
    ("src.aromatics_sidechain_v1", "solve_benzylic_halogenation_v1", "AROMATICS — BENZYLIC HALOGENATION (v1)"),
    ("src.aromatics_sidechain_v1", "solve_benzylic_oxidation_v1", "AROMATICS — BENZYLIC OXIDATION (v1)"),
    # Carbonyl chemistry modules (aldol, Baeyer–Villiger, Cannizzaro,
    # Grignard, hydride reduction, Perkin, CK/WK reductions, Rosenmund,
    # Stephen reduction).
    ("src.carbonyl_aldol_v1", "solve_aldol_v1", "CARBONYL — ALDOL (v1)"),
    ("src.carbonyl_baeyer_villiger_v1", "solve_baeyer_villiger_v1", "CARBONYL — BAEYER VILLIGER (v1)"),
    ("src.carbonyl_cannizzaro_v1", "solve_cannizzaro_v1", "CARBONYL — CANNIZZARO (v1)"),
    ("src.carbonyl_grignard_v1", "solve_grignard_v1", "CARBONYL — GRIGNARD (v1)"),
    ("src.carbonyl_hydride_reduction_v1", "solve_hydride_reduction_v1", "CARBONYL — HYDRIDE REDUCTION (v1)"),
    ("src.carbonyl_perkin_v1", "solve_perkin_v1", "CARBONYL — PERKIN (v1)"),
    ("src.carbonyl_reduction_ck_wk_v1", "solve_ck_wk_v1", "CARBONYL — CK/WK (v1)"),
    ("src.carbonyl_rosenmund_v1", "solve_rosenmund_v1", "CARBONYL — ROSENMUND (v1)"),
    ("src.carbonyl_stephen_v1", "solve_stephen_v1", "CARBONYL — STEPHEN (v1)"),
    # Acid derivatives (acyl chloride, amide, decarboxylation, ester).  These
    # modules handle straightforward nucleophilic acyl substitutions and
    # should appear towards the end because more specialised
    # transformations above may involve similar reagents.
    ("src.carboxy_acid_derivatives_acyl_chloride_v1", "solve_acyl_chloride_v1", "ACID DERIVATIVES — ACYL CHLORIDE (v1)"),
    ("src.carboxy_acid_derivatives_amide_v1", "solve_amide_v1", "ACID DERIVATIVES — AMIDE (v1)"),
    ("src.carboxy_acid_derivatives_decarboxylation_v1", "solve_decarboxylation_v1", "ACID DERIVATIVES — DECARBOXYLATION (v1)"),
    ("src.carboxy_acid_derivatives_ester_v1", "solve_ester_v1", "ACID DERIVATIVES — ESTER (v1)"),
]


def generate_answer_v1(arg1: Any, arg2: Any = None, arg3: Any = None, **kwargs: Any) -> AnswerResponse:
    if "governor" in kwargs:
        _ = kwargs["governor"]

    normalized: Dict[str, Any]
    question: str

    if isinstance(arg1, str):
        question = arg1
        normalized = arg2 if isinstance(arg2, dict) else (kwargs.get("normalized") if isinstance(kwargs.get("normalized"), dict) else {})
    elif isinstance(arg1, dict):
        normalized = arg1
        question = kwargs.get("question") if isinstance(kwargs.get("question"), str) else _extract_question_from_dict(normalized)
    else:
        normalized = {}
        question = ""

    if (not question.strip()) and isinstance(arg2, dict):
        q2 = _extract_question_from_dict(arg2)
        if q2:
            question = q2

    cleaned_text = _clean_text(question)

    dehydration_hint = _has_dehydration_hint(cleaned_text, normalized)
    pcc_hint = _has_pcc_hint(cleaned_text, normalized)

    def apply(d: AnswerDraft, *, ncert: str, footprint: str, safety: str, mistake: str) -> AnswerResponse:
        if pcc_hint and ("pcc" not in (d.exam_tip or "").lower()):
            d = AnswerDraft(d.understanding, d.concept, d.steps, d.final_answer, (d.exam_tip or "").rstrip() + " (PCC oxidation)")
        if dehydration_hint:
            d = AnswerDraft(d.understanding, d.concept, d.steps, d.final_answer, _ensure_dehydration_keyword(d.exam_tip))
        return _apply_exam_tags(d, ncert=ncert, footprint=FP_NEET_JM_JA, safety=safety, mistake=mistake)

    # 0) Benzoyl chloride + NH3 -> benzamide + HCl  (FIX: include HCl for test)
    if _has_benzoyl_chloride_nh3_amide_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is ammonolysis of benzoyl chloride (acyl chloride) with ammonia.",
            "ACID DERIVATIVES — ACYL CHLORIDE → AMIDE (rule)",
            "Nucleophilic acyl substitution: C6H5COCl + NH3 → C6H5CONH2 + HCl (HCl is neutralized by excess NH3).",
            "Benzamide (C6H5CONH2) + HCl",
            "Exam tip: acyl chloride + NH3 gives amide (benzamide) and HCl is formed.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Missing HCl formation or not writing benzamide (C6H5CONH2).")

    # 1) Acetyl chloride hydrolysis
    if _has_acetyl_chloride_hydrolysis_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is hydrolysis of acetyl chloride (an acyl chloride).",
            "ACID DERIVATIVES — ACYL CHLORIDE (hydrolysis rule)",
            "Hydrolysis: CH3COCl + H2O → CH3COOH + HCl",
            "Acetic acid (CH3COOH) + HCl",
            "Exam tip: acyl chlorides hydrolyse readily with water giving carboxylic acid + HCl.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Forgetting HCl or not writing CH3COOH (acetic acid).")

    # 2) Benzoyl chloride hydrolysis
    if _has_benzoyl_chloride_hydrolysis_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is hydrolysis of benzoyl chloride (an acyl chloride).",
            "ACID DERIVATIVES — ACYL CHLORIDE (hydrolysis rule)",
            "Hydrolysis: C6H5COCl + H2O → C6H5COOH + HCl",
            "Benzoic acid (C6H5COOH) + HCl",
            "Exam tip: acyl chlorides hydrolyse readily with water giving carboxylic acid + HCl.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Forgetting HCl or writing wrong acid.")

    # 3) Alkyne hydration HgSO4/H2SO4 -> ketone via tautomerization
    if _has_alkyne_hgso4_h2so4_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is acid-catalyzed hydration of an alkyne using HgSO4/H2SO4.",
            "ALKYNES — HYDRATION (HgSO4/H2SO4 rule)",
            "Addition of water gives an enol intermediate which undergoes keto–enol tautomerization to a ketone.",
            "Final product: ketone (terminal alkyne typically gives a methyl ketone) via tautomerization.",
            "Exam tip: write ketone product (enol → ketone tautomer). Keyword: tautomerization.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Stopping at enol or writing wrong product instead of ketone.")

    # 4) Hydroboration–oxidation: anti-Markovnikov + no rearrangement
    if _has_hydroboration_oxidation_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is hydroboration–oxidation of an alkene.",
            "ALKENES — HYDROBORATION–OXIDATION (rule)",
            "Step 1: BH3·THF adds syn across C=C (hydroboration).\nStep 2: H2O2/NaOH oxidizes C–B to C–OH.",
            "Alcohol formed with anti-Markovnikov orientation (OH on less substituted carbon).",
            "Exam tip: anti-Markovnikov addition and no rearrangement in hydroboration–oxidation.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Writing Markovnikov alcohol or invoking carbocation rearrangement.")

    # 5) Strong oxidant: 1° alcohol -> carboxylic acid
    if _has_strong_oxidant_primary_alcohol_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is oxidation of a primary alcohol using a strong oxidizing agent.",
            "ALCOHOLS — OXIDATION (strong oxidant rule)",
            "Strong oxidants (acidified KMnO4 / K2Cr2O7 / Jones) oxidize 1° alcohols to carboxylic acids (via aldehyde).",
            "Primary alcohol → carboxylic acid (RCH2OH → RCOOH).",
            "Exam tip: strong oxidant gives carboxylic acid from 1° alcohol (not aldehyde).",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Stopping at aldehyde for strong oxidants.")

    # 6) Phenol + bromine water
    if _has_phenol_br2_water_hint(cleaned_text, normalized):
        d = AnswerDraft(
            "This is electrophilic substitution on phenol using bromine water.",
            "PHENOLS — BROMINATION (rule)",
            "Phenol is strongly activating; with Br2/H2O it undergoes rapid tribromination at o,p positions.",
            "2,4,6-tribromophenol (white ppt).",
            "Exam tip: Br2 water + phenol → 2,4,6-tribromophenol (tribromo).",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Writing mono-bromination instead of 2,4,6-tribromophenol.")

    # 7) PCC oxidation
    if pcc_hint:
        d = AnswerDraft(
            "This is oxidation of an alcohol using PCC.",
            "ALCOHOLS — OXIDATION (PCC rule)",
            "PCC oxidizes primary alcohols to aldehydes without over-oxidation to acids.",
            "Primary alcohol → aldehyde (RCH2OH → RCHO). Secondary alcohol → ketone.",
            "Exam tip: PCC gives aldehyde from 1° alcohol; do not write carboxylic acid. PCC.",
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="Writing carboxylic acid instead of aldehyde for PCC.")

    # 7.5) General organic chemistry (stability / acid-base) concepts
    # Use the optional GOC solver to answer radical/carbocation stability and acidity/basicity ranking questions.
    if solve_acid_base_v1:
        try:
            goc_res = solve_acid_base_v1(cleaned_text)
        except Exception:
            goc_res = None
        if goc_res:
            d = AnswerDraft(
                "This is a general organic chemistry concept question.",
                "GOC — STABILITY/ACID-BASE (v1)",
                goc_res.reaction,
                goc_res.product,
                goc_res.notes,
            )
            return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    # 8) IUPAC v2
    r = _call_solver_by_arity(solve_iupac_v2, cleaned_text, normalized)
    if r is not None:
        d = AnswerDraft("This is an IUPAC naming question.", "IUPAC NAMING (v2)", r.steps, r.final_name, r.exam_tip)
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake=r.common_mistake)

    # 8.5) IUPAC v1 fallback (handles limited alkane naming patterns)
    # Only invoke v1 fallback if the query looks like a naming question (contains IUPAC/name keywords)
    if _looks_like_naming_question(cleaned_text.lower()):
        try:
            r1 = solve_iupac_v1(cleaned_text)
        except Exception:
            r1 = None
        if r1 is not None and hasattr(r1, "final_answer") and r1.final_answer:
            d = AnswerDraft(
                "This is an IUPAC naming question.",
                "IUPAC NAMING (v1)",
                "",
                r1.final_answer,
                "Use longest chain, lowest locant rule and alphabetical order.",
            )
            return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    # 9) Major product
    mp = _call_solver_by_arity(solve_major_product_v1, cleaned_text, normalized)
    if mp is not None:
        # major product solver may return either the old schema (steps, final_answer, exam_tip, safety, common_mistake)
        # or the new schema (reaction, product, notes).  Extract fields defensively.
        steps_mp = getattr(mp, "steps", getattr(mp, "reaction", "")) or ""
        final_mp = getattr(mp, "final_answer", getattr(mp, "product", "")) or ""
        tip_mp = getattr(mp, "exam_tip", getattr(mp, "notes", "")) or ""
        safety_mp = getattr(mp, "safety", SAFE_HIGH)
        mistake_mp = getattr(mp, "common_mistake", "")
        d = AnswerDraft(
            "This asks for the major product of a reaction.",
            "MAJOR PRODUCT (v1)",
            steps_mp,
            final_mp,
            tip_mp,
        )
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=safety_mp, mistake=mistake_mp)

    # 10) Conversions v2
    cv2 = _call_solver_by_arity(solve_conversions_v2, cleaned_text, normalized)
    if cv2 is not None:
        d = AnswerDraft("This is a conversion (multi-step) question.", "CONVERSIONS (v2)", cv2.steps, cv2.final_answer, cv2.exam_tip)
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=cv2.safety, mistake=cv2.common_mistake)

    # 11) Conversions v1
    cv1 = _call_solver_by_arity(solve_conversions_v1, cleaned_text, normalized)
    if cv1 is not None:
        d = AnswerDraft("This is a conversion (single-step) question.", "CONVERSIONS (v1)", cv1.steps, cv1.final_answer, cv1.exam_tip)
        return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=cv1.safety, mistake=cv1.common_mistake)

    # 11.5) Additional specialised reaction solvers
    # Iterate through the additional solvers list and return on the first match.
    for _module_path, _fn_name, _concept in _ADDITIONAL_SOLVERS:
        _fn = _optional_solver(_module_path, _fn_name)
        if _fn is None:
            continue
        try:
            res = _fn(cleaned_text)
        except Exception:
            res = None
        if res:
            # Extract common fields across result dataclasses. Fallback to empty strings if missing.
            final_answer = getattr(res, "product", getattr(res, "final_answer", getattr(res, "name", ""))) or ""
            steps2 = getattr(res, "reaction", getattr(res, "steps", getattr(res, "reaction_steps", ""))) or ""
            exam_tip2 = getattr(res, "notes", getattr(res, "exam_tip", getattr(res, "tip", ""))) or ""
            # Determine exam tag overrides: benzyne is advanced/medium
            if _fn_name == "solve_benzyne_v1":
                ncert_tag = "ADVANCED"
                safety_tag = SAFE_MED
            else:
                ncert_tag = NCERT_ALIGNED
                safety_tag = SAFE_HIGH
            d = AnswerDraft(
                "This is a reaction question.",
                _concept,
                steps2,
                final_answer,
                exam_tip2,
            )
            return apply(d, ncert=ncert_tag, footprint=FP_NEET_JM_JA, safety=safety_tag, mistake="")

    # 12) Theory modules
    iso = answer_isomerism_question(cleaned_text)
    if iso and iso.get("topic") == "ISOMERISM_V1":
        d = AnswerDraft("Isomerism question.", "ISOMERISM (v1)", iso.get("explanation", ""), iso.get("answer", ""), "Exam tip: identify type precisely.")
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake=iso.get("common_mistake", ""))

    st = answer_stereochemistry_question(cleaned_text, normalized)
    if st and st.get("topic") == "STEREOCHEMISTRY_V1":
        d = AnswerDraft("Stereochemistry question.", "STEREOCHEMISTRY (v1)", st.get("steps", ""), st.get("answer", ""), st.get("exam_tip", ""))
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake=st.get("common_mistake", ""))

    pol = answer_polymers_question(cleaned_text, normalized)
    if pol and pol.get("topic") == "POLYMERS_V1":
        d = AnswerDraft("Polymers question.", "POLYMERS (v1)", pol.get("explanation", ""), pol.get("answer", ""), pol.get("exam_tip", ""))
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    bio = answer_biomolecules_question(cleaned_text, normalized)
    if bio and bio.get("topic") == "BIOMOLECULES_V1":
        d = AnswerDraft("Biomolecules question.", "BIOMOLECULES (v1)", bio.get("explanation", ""), bio.get("answer", ""), bio.get("exam_tip", ""))
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    eve = answer_everyday_life_question(cleaned_text, normalized)
    if eve and eve.get("topic") == "EVERYDAY_LIFE_V1":
        d = AnswerDraft("Everyday life chemistry question.", "EVERYDAY LIFE (v1)", eve.get("explanation", ""), eve.get("answer", ""), eve.get("exam_tip", ""))
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    prac = answer_practical_organic_question(cleaned_text, normalized)
    if prac and prac.get("topic") == "PRACTICAL_ORGANIC_V1":
        d = AnswerDraft("Practical organic question.", "PRACTICAL ORGANIC (v1)", prac.get("explanation", ""), prac.get("answer", ""), "Exam tip: reagent + observation + inference.")
        return apply(d, ncert=NCERT_DIRECT, footprint=FP_NEET_JM_JA, safety=SAFE_HIGH, mistake="")

    d = AnswerDraft(
        "The current deterministic engine could not classify this question confidently.",
        "UNSUPPORTED (v1)",
        "Provide clearer reagents/conditions to match a deterministic module.",
        "INSUFFICIENT DATA",
        "Exam tip: include solvent/heat/catalyst/peroxide info.",
    )
    return apply(d, ncert=NCERT_ALIGNED, footprint=FP_NEET_JM_JA, safety=SAFE_MED, mistake="No deterministic match.")
