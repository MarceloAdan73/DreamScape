"""Título instantáneo (provisorio) para un sueño recién registrado.

El análisis con IA tarda ~1 min en CPU; para que el sueño tenga nombre al
instante se genera un título local y determinista con las palabras clave del
relato. Cuando el análisis termina, el título artístico del LLM lo reemplaza
(`analyzer._do_analysis`).

Sin dependencias externas: tokenización por regex, stopwords en español y
conteo de frecuencia (con desempate por primera aparición).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_WORD_RE = re.compile(r"[a-záéíóúñü]+")

# Español, sin tildes (se comparan normalizadas). Artículos, pronombres,
# preposiciones, conjunciones, adverbios comunes y conjugaciones frecuentes
# de ser/estar/haber/tener/hacer/decir/ir/ver/dar/poder/querer/parecer.
_STOPWORDS = frozenset(
    """  # noqa: SIM905
    el la los las un una unos unas
    este esta estos estas ese esa esos esas
    aquel aquella aquellos aquellas esto eso aquello
    mi mis tu tus su sus nuestro vuestro
    cada otro otra otros otras
    todo toda todos todas tanto tanta tantos tantas
    mismo misma cual cuales cuanto cuanta cuantos cuantas
    algun alguna algunos algunas ningun ninguna
    poco poca pocos pocas mucho mucha muchos muchas
    demas tal tales
    a ante bajo con contra de desde en entre hacia hasta para por segun sin
    sobre tras durante mediante del al
    y e ni o u pero mas sino porque pues aunque que si como cuando donde
    mientras hasta
    yo tu ella nosotros vosotros ellos ellas usted ustedes
    me te se nos os lo la los las le les mi ti si consigo conmigo contigo
    quien quienes cuyo cuya cuyos aquellas
    no muy mas menos tan asi aqui ahi alli aca alla
    ahora antes despues luego entonces siempre nunca jamas tambien tampoco
    aun todavia ya hoy ayer manana bien mal mejor peor quizas quiza acaso
    apenas casi solo unicamente ademas encima debajo dentro fuera cerca lejos
    enfrente detras delante alrededor junto excepto salvo incluso
    es son era eran fue fueron sea sean sido siendo
    estoy estas esta estamos estan estaba estaban estado estando
    he has ha hemos han habia habian habido habiendo
    tengo tienes tiene tenemos tienen tenia tenian tenido teniendo
    hago haces hace hacemos hacen hacia hacian hecho haciendo
    digo dices dice decimos dicen decia decian dicho diciendo
    voy vas vamos van iba iban ido yendo
    veo ves ve vemos ven veia veian visto viendo
    doy das damos dan daba daban dado dando
    puedo puedes puede podemos pueden podia podian podido pudiendo
    quiero quieres quiere queremos quieren queria querian querido queriendo
    se sabes sabe sabemos saben sabia sabian sabido sabiendo
    parece parecen parecia parecian parecido hay estoy estan
    sonar sueno suena sonaba sone sonado sonando
    ver veo ves ve vemos ven veia veiamos visto viendo
    mirar miro miras mira miramos miran miraba miraban mirado mirando
    dormir duermo duermes duerme dormimos duermen dormia dormido durmiendo
    despertar despierto despiertas despierta despertamos despiertan
    despertaba desperte despertado despertando
    correr corro corres corre corremos corren corria corrido corriendo
    caminar camino caminas camina caminamos caminan caminaba caminado caminando
    volar vuelo vuelas vuela volamos vuelan volaba volado volando
    caer caigo caes cae caemos caen caia caido cayendo
    perseguir persigo persigue persiguen perseguia perseguido persiguiendo
    escapar escapo escapas escapa escapan escapaba escapado escapando
    huir huyo huyes huye huyen huia huido huyendo
    buscar busco buscas busca buscan buscaba buscado buscando
    encontrar encuentro encuentras encuentra encuentran encontrado encontrando
    perder pierdo pierdes pierde pierden perdido perdiendo
    comer como comes come comen comido comiendo
    hablar hablo hablas habla hablan hablado hablando
    gritar grito gritas grita gritan gritado gritando
    llorar lloro lloras llora lloran llorado llorando
    reir rio ries rie rien reia reido riendo
    abrazar abrazas abraza abrazan abrazado abrazando
    besar besas besa besan besado besando
    cuidar cuido cuidas cuida cuidan cuidado cuidando cuidaba cuidabas cuidabamos cuidaban
    sentir siento sientes siente sienten sentido sintiendo
    creer creo crees cree creemos creen creia creian creido creyendo
    pensar pienso piensas piensa pensamos piensan pensaba pensaban pensado pensando
    recordar recuerdo recuerdas recuerda recuerdan recordaba recordaban recordado recordando
    olvidar olvido olvidas olvida olvidan olvidaba olvidaban olvidado olvidando
    querer quiero quieres quiere queremos quieren queria querian querido queriendo
    poder puedo puedes puede podemos pueden podia podian podido pudiendo
    vez veces cosa cosas algo alguien nadie nada lado momento forma manera
    tipo gran grande grandes pequeno pequena pequenos pequenas
    nuevo nueva nuevos nuevas viejo vieja primer primero ultimo
    """.split()
)


def _base(word: str) -> str:
    """Minúsculas sin tildes para comparar y contar (`canción` → `cancion`)."""
    lowered = word.lower()
    return "".join(
        char for char in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(char) != "Mn"
    )


def keywords(text: str, limit: int = 3) -> list[str]:
    """Palabras clave del relato (frecuencia, desempate por primera aparición)."""
    words = _WORD_RE.findall(text.lower())
    if not words:
        return []
    display: dict[str, str] = {}
    bases: list[str] = []
    for word in words:
        base = _base(word)
        if len(base) < 3 or base in _STOPWORDS:
            continue
        display.setdefault(base, word)
        bases.append(base)
    if not bases:
        return []
    freq = Counter(bases)
    first_seen: dict[str, int] = {}
    for index, base in enumerate(bases):
        first_seen.setdefault(base, index)
    ranked = sorted(freq, key=lambda base: (-freq[base], first_seen[base]))
    return [display[base] for base in ranked[:limit]]


def make_instant_title(text: str) -> str | None:
    """Título provisorio con las palabras clave (`Gato, crías y pareja`).

    Solo la primera palabra va en mayúscula (estilo español).
    Devuelve `None` si el relato no tiene palabras con contenido.
    """
    words = keywords(text)
    if not words:
        return None
    parts = [words[0].capitalize()] + [word.lower() for word in words[1:]]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} y {parts[1]}"
    return f"{parts[0]}, {parts[1]} y {parts[2]}"
