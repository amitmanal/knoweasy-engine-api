# src/alkenes_alkynes_additions_v1.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class AlkeneAlkyneResult:
    reaction: str
    product: str
    notes: str = ""


def _lc(s: str) -> str:
    return (s or "").strip().lower()


def _has_any(t: str, words: list[str]) -> bool:
    return any(w in t for w in words)


def _is_hydrocarbon_context(t: str) -> bool:
    # Broad triggers for alkenes/alkynes
    if _has_any(t, ["alkene", "alkyne", "olefin", "double bond", "triple bond"]):
        return True
    if _has_any(t, ["ethene", "propene", "butene", "acetylene", "ethyne", "propyne", "butyne"]):
        return True
    if re.search(r"\bc2h4\b|\bc3h6\b|\bc2h2\b|\bc3h4\b", t):
        return True
    # Reagent patterns typical to addition chemistry
    if _has_any(t, ["hbr", "hcl", "hi", "br2", "cl2", "h2so4", "h2o", "kmno4", "o3", "ozonolysis", "bh3", "borane", "h2o2", "h2so4/hgso4", "hgso4"]):
        return True
    return False


def _is_concept_order_question(t: str) -> bool:
    return _has_any(t, ["markovnikov", "anti-markovnikov", "peroxide effect", "kharasch", "orientation", "which is major"])


def _is_alkyne(t: str) -> bool:
    return _has_any(t, ["alkyne", "ethyne", "acetylene", "propyne", "butyne", "triple bond"]) or ("c2h2" in t) or ("c3h4" in t)


def _is_alkene(t: str) -> bool:
    return _has_any(t, ["alkene", "ethene", "propene", "butene", "double bond"]) or ("c2h4" in t) or ("c3h6" in t)


def solve_alkenes_alkynes_v1(text: str) -> Optional[AlkeneAlkyneResult]:
    """
    Alkenes & Alkynes v1 (exam-safe):
      - HX addition: Markovnikov vs anti-Markovnikov (only HBr with peroxides)
      - Hydration: acid-catalyzed (Markovnikov), hydroboration-oxidation (anti-Markovnikov)
      - Halogen addition: Br2/Cl2 gives vicinal dihalide (alkenes)
      - KMnO4: cold (diol), hot (cleavage) [rule-level]
      - Alkynes: hydration (HgSO4/H2SO4 → ketone; terminal → methyl ketone),
                hydroboration oxidation (terminal → aldehyde), HX addition (vinyl/geminal)
      - Terminal alkyne acidity: NaNH2 forms acetylide
    """
    t = _lc(text)
    if not _is_hydrocarbon_context(t):
        return None

    # ------------------------------------------------------------------
    # Specific named-substrate cases (propene, ethene, propyne etc.)
    # These blocks return explicit product names rather than generic
    # "Markovnikov product" to satisfy deterministic unit tests.
    # They are checked before the more general rule-level patterns below.

    # Acid-catalyzed hydration / oxymercuration of propene
    if _has_any(t, ["propene", "propylene", "ch3ch=ch2", "c3h6"]):
        # Acid hydration (dilute H2SO4)
        if _has_any(t, ["h2o", "water"]) and _has_any(t, ["h2so4", "acid", "h+"]):
            return AlkeneAlkyneResult(
                reaction="Propene hydration (acid-catalyzed)",
                product="propan-2-ol",
                notes="Markovnikov hydration of propene gives isopropanol (propan-2-ol).",
            )
        # Oxymercuration-demercuration (Hg(OAc)2/H2O then NaBH4)
        if _has_any(t, ["hg(oac)2", "oxymercuration", "mercuric acetate", "hg(oac)2/h2o", "hgso4"]):
            return AlkeneAlkyneResult(
                reaction="Propene oxymercuration–demercuration",
                product="propan-2-ol",
                notes="Markovnikov addition without carbocation rearrangement (no rearrangement).",
            )
        # Hydroboration–oxidation
        if _has_any(t, ["bh3", "diborane", "borane", "hydroboration"]) and _has_any(t, ["h2o2", "naoh", "oh-"]):
            return AlkeneAlkyneResult(
                reaction="Propene hydroboration–oxidation",
                product="propan-1-ol",
                notes="Anti-Markovnikov addition: BH3/THF followed by H2O2/NaOH gives propan-1-ol.",
            )
        # HBr addition (with or without peroxide)
        if _has_any(t, ["hbr"]):
            # Peroxide effect (anti-Markovnikov)
            if _has_any(t, ["peroxide", "roor", "h2o2", "kharasch"]):
                return AlkeneAlkyneResult(
                    reaction="Propene + HBr (peroxide effect)",
                    product="1-bromopropane",
                    notes="Anti-Markovnikov radical addition of HBr in presence of peroxides.",
                )
            # Default Markovnikov addition
            return AlkeneAlkyneResult(
                reaction="Propene + HBr",
                product="2-bromopropane",
                notes="Electrophilic addition of HBr gives Markovnikov product (2-bromopropane).",
            )
        # Bromine addition (solvent-specific) handled by br2_addition module

    # Hydroboration–oxidation of ethene
    if _has_any(t, ["ethene", "ethylene", "c2h4", "ch2=ch2"]):
        if _has_any(t, ["bh3", "diborane", "borane", "hydroboration"]) and _has_any(t, ["h2o2", "naoh", "oh-"]):
            return AlkeneAlkyneResult(
                reaction="Ethene hydroboration–oxidation",
                product="ethanol",
                notes="Anti-Markovnikov hydration of ethene yields ethanol.",
            )

    # KMnO4 specific cases: propene and 2-butene
    if _has_any(t, ["kmno4", "kmno₄", "permanganate"]):
        # Propene
        if _has_any(t, ["propene", "propylene", "ch3ch=ch2", "c3h6"]):
            cold = _has_any(t, ["cold", "dilute", "alkaline", "baeyer"])
            hot = _has_any(t, ["hot", "heated", "acidic", "strong"])
            if cold:
                return AlkeneAlkyneResult(
                    reaction="Propene + cold dilute KMnO4",
                    product="propane-1,2-diol",
                    notes="Cold, dilute alkaline KMnO4 (Baeyer test) gives vicinal diol.",
                )
            if hot:
                return AlkeneAlkyneResult(
                    reaction="Propene + hot KMnO4",
                    product="CH3COOH + CO2",
                    notes="Hot/acidic KMnO4 cleaves the double bond: propene → acetic acid + CO2.",
                )
        # 2-butene
        if _has_any(t, ["2-butene", "but-2-ene", "butene-2", "ch3ch=chch3", "c4h8"]):
            if _has_any(t, ["hot", "heated", "acidic", "strong"]):
                return AlkeneAlkyneResult(
                    reaction="2-Butene + hot KMnO4",
                    product="2 CH3COOH",
                    notes="Oxidative cleavage of symmetrical internal alkene gives two acetic acid molecules.",
                )

    # Ozonolysis specific case: propene
    if _has_any(t, ["ozone", "o3", "ozonolysis"]):
        if _has_any(t, ["propene", "propylene", "ch3ch=ch2", "c3h6"]):
            reductive = _has_any(t, ["zn", "zn/h2o", "dimethyl sulfide", "dms"])  # reductive workup
            oxidative = _has_any(t, ["h2o2", "oxidative"])
            if reductive:
                return AlkeneAlkyneResult(
                    reaction="Propene ozonolysis (reductive workup)",
                    product="CH3CHO + HCHO",
                    notes="Ozonolysis of propene followed by Zn/H2O or DMS yields acetaldehyde and formaldehyde.",
                )
            if oxidative:
                return AlkeneAlkyneResult(
                    reaction="Propene ozonolysis (oxidative workup)",
                    product="CH3COOH",
                    notes="Oxidative workup (H2O2) oxidizes acetaldehyde to acetic acid.",
                )

    # Alkyne specific cases: propyne
    if _has_any(t, ["propyne", "ch3c≡ch", "ch3c#ch", "c3h4"]):
        # HgSO4/H2SO4 hydration → ketone (acetone).
        # Require the presence of mercuric catalyst or sulfuric acid explicitly; avoid matching on plain H2O/H2O2.
        if _has_any(t, ["hgso4", "hg2+", "mercuric", "h2so4"]):
            return AlkeneAlkyneResult(
                reaction="Propyne hydration (HgSO4/H2SO4)",
                product="acetone",
                notes="Acid-catalyzed hydration of propyne gives an enol which tautomerizes to acetone.",
            )
        # Hydroboration–oxidation → aldehyde (propanal)
        if _has_any(t, ["bh3", "diborane", "borane", "hydroboration"]) and _has_any(t, ["h2o2", "naoh", "oh-"]):
            return AlkeneAlkyneResult(
                reaction="Propyne hydroboration–oxidation",
                product="propanal",
                notes="Anti-Markovnikov hydration of propyne gives propanal after tautomerization.",
            )

    # End of specific cases

    # 1) Markovnikov vs anti-Markovnikov (HBr + peroxide)
    if _has_any(t, ["hbr"]) and (_is_alkene(t) or _is_concept_order_question(t)):
        if _has_any(t, ["peroxide", "roor", "h2o2", "kharasch"]):
            return AlkeneAlkyneResult(
                reaction="Anti-Markovnikov addition of HBr (peroxide effect / Kharasch)",
                product="Alkene + HBr (ROOR) → **anti-Markovnikov bromoalkane** (radical addition).",
                notes="Exam trap: peroxide effect works for **HBr only** (not HCl/HI).",
            )
        return AlkeneAlkyneResult(
            reaction="Markovnikov addition of HX (electrophilic addition)",
            product="Alkene + HX → **Markovnikov product** (X on more substituted carbon).",
            notes="Orientation: Markovnikov (no peroxides).",
        )

    # 2) Hydration of alkenes
    if (_is_alkene(t) or "alkene" in t) and _has_any(t, ["h2o", "hydration"]) and _has_any(t, ["h2so4", "h+", "acid"]):
        return AlkeneAlkyneResult(
            reaction="Acid-catalyzed hydration of alkene",
            product="Alkene + H2O (H+, dil. H2SO4) → **Markovnikov alcohol**.",
            notes="Trap: rearrangement possible in carbocation pathway (concept).",
        )

    if (_is_alkene(t) or "alkene" in t) and _has_any(t, ["bh3", "borane", "hydroboration"]) and _has_any(t, ["h2o2", "oh-", "naoh"]):
        return AlkeneAlkyneResult(
            reaction="Hydroboration–oxidation of alkene",
            product="Alkene + BH3; then H2O2/ OH− → **anti-Markovnikov alcohol** (no rearrangement).",
            notes="Exam key: anti-Markovnikov hydration without rearrangement.",
        )

    # 3) Halogen addition to alkenes
    if (_is_alkene(t) or "alkene" in t) and _has_any(t, ["br2", "cl2"]) and not _is_alkyne(t):
        return AlkeneAlkyneResult(
            reaction="Halogen addition to alkene",
            product="Alkene + Br2/Cl2 → **vicinal dihalide (1,2-dihalide)**.",
            notes="Typical electrophilic addition via halonium ion.",
        )

    # 4) KMnO4 oxidation rules (alkenes)
    if _has_any(t, ["kmno4", "kmno₄", "permanganate"]) and (_is_alkene(t) or "double bond" in t):
        if _has_any(t, ["cold", "dilute", "baeyer", "alkaline", "oh-"]):
            return AlkeneAlkyneResult(
                reaction="Baeyer test / cold KMnO4 oxidation (alkene)",
                product="Alkene + cold, dilute alkaline KMnO4 → **vicinal diol (glycol)**.",
                notes="Exam trap: cold KMnO4 gives diol; hot KMnO4 gives cleavage.",
            )
        if _has_any(t, ["hot", "heat", "acidic", "strong"]):
            return AlkeneAlkyneResult(
                reaction="Hot KMnO4 oxidative cleavage (alkene)",
                product="Alkene + hot KMnO4 → **oxidative cleavage** (carbonyl/acid depending on substitution).",
                notes="Rule: terminal C=C often gives CO2/acid; internal gives ketones/acids depending on H.",
            )
        return AlkeneAlkyneResult(
            reaction="KMnO4 oxidation of alkene (condition-dependent)",
            product="Cold, dilute alkaline KMnO4 → **diol**; hot KMnO4 → **cleavage**.",
            notes="State condition to decide product.",
        )

    # 5) Ozonolysis
    if _has_any(t, ["o3", "ozone", "ozonolysis"]) and (_is_alkene(t) or "alkene" in t):
        if _has_any(t, ["zn", "znh2o", "dimethyl sulfide", "dms", "reductive"]):
            return AlkeneAlkyneResult(
                reaction="Ozonolysis of alkene (reductive workup)",
                product="Alkene + O3; then Zn/H2O (or DMS) → **aldehydes/ketones** (no further oxidation).",
                notes="Exam trap: reductive workup stops at aldehydes/ketones.",
            )
        if _has_any(t, ["h2o2", "oxidative"]):
            return AlkeneAlkyneResult(
                reaction="Ozonolysis of alkene (oxidative workup)",
                product="Alkene + O3; then H2O2 → **acids/ketones** (aldehydes oxidize to acids).",
                notes="Exam trap: oxidative workup converts aldehyde fragments to acids.",
            )
        return AlkeneAlkyneResult(
            reaction="Ozonolysis of alkene (workup dependent)",
            product="O3 cleavage gives carbonyl fragments; **reductive** → aldehyde/ketone; **oxidative** → acids/ketones.",
            notes="Mention workup to be exam-safe.",
        )

    # 6) Alkynes: acidity (terminal)
    if _is_alkyne(t) and _has_any(t, ["nanh2", "na nh2", "sodamide", "na metal", "acetylide", "terminal alkyne", "acidity"]):
        return AlkeneAlkyneResult(
            reaction="Terminal alkyne acidity / acetylide formation",
            product="RC≡CH + NaNH2 → **RC≡C⁻ Na⁺ (acetylide)** + NH3.",
            notes="Exam key: terminal alkynes are acidic (sp-hybridized); acetylide is strong nucleophile.",
        )

    # 7) Alkynes: hydration (HgSO4/H2SO4)
    if _is_alkyne(t) and _has_any(t, ["hgso4", "h2so4", "hydration", "h2o"]):
        return AlkeneAlkyneResult(
            reaction="Hydration of alkyne (HgSO4/H2SO4)",
            product="Alkyne + H2O (HgSO4/H2SO4) → enol → **ketone (Markovnikov)**. Terminal alkyne → **methyl ketone**.",
            notes="Exam trap: enol tautomerizes to ketone.",
        )

    # 8) Alkynes: hydroboration oxidation
    if _is_alkyne(t) and _has_any(t, ["hydroboration", "bh3", "borane"]) and _has_any(t, ["h2o2", "oh-", "naoh"]):
        return AlkeneAlkyneResult(
            reaction="Hydroboration–oxidation of alkyne",
            product="Terminal alkyne → **aldehyde** (anti-Markovnikov) after oxidation; internal → ketone.",
            notes="Exam key: hydroboration gives anti-Markovnikov hydration equivalent.",
        )

    # 9) Alkynes: HX addition (rule-level)
    if _is_alkyne(t) and _has_any(t, ["hbr", "hcl", "hi"]) and _has_any(t, ["1 eq", "one equivalent", "excess", "2 eq", "two equivalent"]):
        if _has_any(t, ["excess", "2 eq", "two"]):
            return AlkeneAlkyneResult(
                reaction="Addition of HX to alkyne (excess)",
                product="Alkyne + excess HX → **geminal dihalide (same carbon)** (Markovnikov).",
                notes="Exam trap: excess HX gives geminal dihalide.",
            )
        return AlkeneAlkyneResult(
            reaction="Addition of HX to alkyne (1 equivalent)",
            product="Alkyne + 1 eq HX → **vinyl halide** (Markovnikov).",
            notes="Exam trap: stops at vinyl halide with 1 eq.",
        )

    return None
