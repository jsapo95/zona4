from __future__ import annotations

from zona4_graph_loader.domain.identity_resolution import (
    SOURCE_PRIORITY,
    resolve_identities,
)


def _persona(key, nombre, fuente, **extra):
    base = {
        "persona_key": key,
        "nombre": nombre,
        "genero": "INDETERMINADO",
        "fuente": fuente,
        "roles": ["VICTIMA"],
    }
    base.update(extra)
    return base


def test_merge_con_nombre_y_fecha_nacimiento_coincidentes():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Carlos Abachian", "detalles_personas",
                     fecha_nacimiento="1950-03-02"),
            _persona("minjus_victima:213", "Juan Carlos Abachian", "minjus_victimas",
                     fecha_nacimiento="1950-03-02"),
        ],
        "eventos_espaciales": [
            {"persona_key": "minjus_victima:213", "lugar_key": "lugar:CCD:x",
             "tipo_relacion": "PRESENTE_EN", "origen": "minjus_victimas"}
        ],
    }
    report = resolve_identities(dataset)

    assert len(dataset["personas"]) == 1
    superviviente = dataset["personas"][0]
    assert superviviente["persona_key"] == "registro:1"
    assert superviviente["claves_alt"] == ["minjus_victima:213"]
    assert superviviente["fuente"] == "detalles_personas|minjus_victimas"
    assert dataset["eventos_espaciales"][0]["persona_key"] == "registro:1"
    assert len(report.merges) == 1
    assert report.candidatos == []


def test_merge_con_fecha_secuestro_coincidente():
    dataset = {
        "personas": [
            _persona("archivo_memoria:7", "Jorge Bellantuono Herrero", "archivo_memoria",
                     fecha_secuestro="1976-07-13"),
            _persona("minjus_victima:900", "Jorge Bellantuono Herrero", "minjus_victimas",
                     fecha_secuestro="1976-07-13"),
        ],
    }
    resolve_identities(dataset)
    assert len(dataset["personas"]) == 1
    assert dataset["personas"][0]["persona_key"] == "archivo_memoria:7"


def test_nombre_igual_sin_fecha_genera_candidato_no_merge():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Perez", "detalles_personas"),
            _persona("minjus_victima:5", "Juan Perez", "minjus_victimas"),
        ],
    }
    report = resolve_identities(dataset)

    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert len(report.candidatos) == 1
    candidato = report.candidatos[0]
    assert candidato["metodo"] == "nombre_exacto_sin_fecha"
    assert candidato["confianza"] == "media"
    assert {candidato["placeholder_key"], candidato["candidate_key"]} == {
        "registro:1", "minjus_victima:5"
    }


def test_fechas_distintas_no_mergean():
    dataset = {
        "personas": [
            _persona("registro:1", "Juan Perez", "detalles_personas",
                     fecha_nacimiento="1950-01-01"),
            _persona("minjus_victima:5", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1962-11-30"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []


def test_nunca_mergea_dos_personas_de_la_misma_fuente():
    dataset = {
        "personas": [
            _persona("minjus_victima:1", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1950-01-01"),
            _persona("minjus_victima:2", "Juan Perez", "minjus_victimas",
                     fecha_nacimiento="1950-01-01"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert report.candidatos == []


def test_hermanas_con_apellido_igual_no_mergean_ni_son_candidatas_fuertes():
    """Caso real de MinJus: dos personas distintas, nombres muy similares."""
    dataset = {
        "personas": [
            _persona("minjus_victima:10", "Abadía Crespo, Dominga", "minjus_victimas"),
            _persona("registro:88", "Abadía Crespo, Felicidad", "detalles_personas"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert all(c["confianza"] != "alta" for c in report.candidatos)


def test_merge_reescribe_relaciones_interpersonales_y_contexto():
    dataset = {
        "personas": [
            _persona("registro:1", "Ana Gomez", "detalles_personas",
                     fecha_nacimiento="1955-05-05"),
            _persona("minjus_victima:2", "Ana Gomez", "minjus_victimas",
                     fecha_nacimiento="1955-05-05"),
        ],
        "relaciones_interpersonales": [
            {"source_key": "minjus_imputado:9", "target_key": "minjus_victima:2",
             "tipo": "TORTURO_A", "fuente": "minjus_victimas"},
        ],
        "relaciones_contexto": [
            {"persona_key": "minjus_victima:2", "entidad_key": "org:jp",
             "tipo_relacion": "PARTE_DE", "origen": "minjus_victimas"},
        ],
    }
    resolve_identities(dataset)
    assert dataset["relaciones_interpersonales"][0]["target_key"] == "registro:1"
    assert dataset["relaciones_contexto"][0]["persona_key"] == "registro:1"


def test_merge_unifica_roles_y_completa_campos_faltantes():
    dataset = {
        "personas": [
            _persona("registro:1", "Luis Diaz", "detalles_personas",
                     fecha_nacimiento="1940-02-02"),
            _persona("juicios_condenado:3", "Luis Diaz", "juicios_condenados",
                     fecha_nacimiento="1940-02-02", roles=["REPRESOR"],
                     fecha_secuestro=None),
        ],
    }
    resolve_identities(dataset)
    superviviente = dataset["personas"][0]
    assert superviviente["roles"] == ["REPRESOR", "VICTIMA"]


def test_prioridad_de_fuente_declarada():
    assert SOURCE_PRIORITY[0] == "detalles_personas"
    assert SOURCE_PRIORITY.index("archivo_memoria") < SOURCE_PRIORITY.index("minjus_victimas")


def test_dataset_sin_personas_no_falla():
    dataset = {"personas": []}
    report = resolve_identities(dataset)
    assert report.merges == []
    assert report.candidatos == []


def test_cadena_transitiva_sin_clique_no_mergea():
    """A-B comparten fecha_nacimiento y B-C comparten fecha_secuestro, pero A y
    C no tienen ningún campo de fecha en común (A no registra fecha_secuestro,
    C no registra fecha_nacimiento): no hay evidencia directa entre ellos, ni a
    favor ni en contra. La componente conexa A-B-C (conectada solo a través de
    B) no es un clique completo porque falta la arista A-C, así que ninguno de
    los tres debe fusionarse. Bajo el criterio pairwise viejo ("admite si CUALQUIER
    miembro del cluster confirma"), los tres habrían colapsado en un solo
    canónico pese a que A y C jamás se confirmaron entre sí.
    """
    dataset = {
        "personas": [
            _persona("registro:1", "Marta Alsina", "detalles_personas",
                     fecha_nacimiento="1950-01-01"),
            _persona("archivo_memoria:2", "Marta Alsina", "archivo_memoria",
                     fecha_nacimiento="1950-01-01", fecha_secuestro="1977-06-01"),
            _persona("minjus_victima:3", "Marta Alsina", "minjus_victimas",
                     fecha_secuestro="1977-06-01"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 3
    assert report.merges == []


def test_fecha_secuestro_contradictoria_veta_merge_y_marca_candidato():
    """Mismo nombre y fecha_nacimiento coincidente, pero fecha_secuestro
    contradictoria: la fecha que no coincide es evidencia de que son dos
    personas distintas y debe vetar el merge, no solo ser ignorada.
    """
    dataset = {
        "personas": [
            _persona("registro:1", "Carlos Ibañez", "detalles_personas",
                     fecha_nacimiento="1945-04-04", fecha_secuestro="1976-03-01"),
            _persona("minjus_victima:5", "Carlos Ibañez", "minjus_victimas",
                     fecha_nacimiento="1945-04-04", fecha_secuestro="1978-11-20"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 2
    assert report.merges == []
    assert len(report.candidatos) == 1
    candidato = report.candidatos[0]
    assert candidato["metodo"] == "nombre_exacto_fecha_contradictoria"
    assert candidato["metodo"] != "nombre_exacto_sin_fecha"
    assert candidato["confianza"] == "baja"


def test_clique_completo_de_tres_fuentes_mergea_a_un_canonico():
    """Los tres pares de un trío se confirman mutuamente por una fecha
    compartida: es un clique completo y la regla más estricta no debe romper
    este merge legítimo entre tres fuentes distintas.
    """
    dataset = {
        "personas": [
            _persona("registro:1", "Pedro Suarez", "detalles_personas",
                     fecha_nacimiento="1948-08-08"),
            _persona("archivo_memoria:2", "Pedro Suarez", "archivo_memoria",
                     fecha_nacimiento="1948-08-08"),
            _persona("minjus_victima:3", "Pedro Suarez", "minjus_victimas",
                     fecha_nacimiento="1948-08-08"),
        ],
    }
    report = resolve_identities(dataset)
    assert len(dataset["personas"]) == 1
    assert dataset["personas"][0]["persona_key"] == "registro:1"
    assert len(report.merges) == 2


def test_merge_que_generaria_self_loop_no_deja_relacion_apuntandose_a_si_misma():
    dataset = {
        "personas": [
            _persona("registro:1", "Rosa Medina", "detalles_personas",
                     fecha_nacimiento="1952-02-14"),
            _persona("minjus_victima:2", "Rosa Medina", "minjus_victimas",
                     fecha_nacimiento="1952-02-14"),
        ],
        "relaciones_interpersonales": [
            # Ambos extremos resuelven al mismo canónico tras el merge: sería
            # un self-loop si no se filtrara.
            {"source_key": "registro:1", "target_key": "minjus_victima:2",
             "tipo": "HERMANA_DE", "fuente": "detalles_personas"},
        ],
    }
    resolve_identities(dataset)
    assert all(
        fila["source_key"] != fila["target_key"]
        for fila in dataset["relaciones_interpersonales"]
    )


def test_absorber_copia_campo_no_listado_y_no_pisa_el_ya_presente():
    dataset = {
        "personas": [
            _persona("registro:1", "Elena Rios", "detalles_personas",
                     fecha_nacimiento="1958-07-07", ocupacion="Docente"),
            _persona("minjus_victima:2", "Elena Rios", "minjus_victimas",
                     fecha_nacimiento="1958-07-07", ocupacion="Estudiante",
                     nacionalidad="Argentina"),
        ],
    }
    resolve_identities(dataset)
    superviviente = dataset["personas"][0]
    # Campo ausente en el canónico: se completa desde el absorbido.
    assert superviviente["nacionalidad"] == "Argentina"
    # Campo ya presente en el canónico: no se pisa con el del absorbido.
    assert superviviente["ocupacion"] == "Docente"
