from services.analise.analise_hipsometria import AnaliseHipsometria
from services.analise.analise_declividade import AnaliseDeclividade
from services.analise.analise_fluxo import AnaliseFluxo
from services.analise.analise_uso_solo import AnaliseUsoSolo
from services.ahp_service import AHPService


class ConfigService:

    def __init__(self, cidade, crs):
        self.cidade = cidade
        self.crs = crs

    def gerar_config(self):
        """
        Gera toda a configuração inicial da análise.

        Essa configuração será:
        - enviada ao frontend
        - exibida na sidebar
        - opcionalmente editada pelo usuário
        """

        return {
            "criterios": {
                "uso_do_solo": {
                    "ativo": True,
                    "classes": self._config_uso_do_solo()
                },

                "declividade": {
                    "ativo": True,
                    "classes": self._config_declividade()
                },

                "fluxo_acumulado": {
                    "ativo": True,
                    "classes": self._config_fluxo()
                },

                "hipsometria": {
                    "ativo": True,
                    "classes": self._config_hipsometria()
                }
            },

            "pesos": self._config_pesos()
        }

    # USO DO SOLO

    def _config_uso_do_solo(self):

        return {
            "vegetacao": {
                "ids": [1, 3, 4, 5, 6, 49, 10, 11, 12, 32, 29, 50],
                "valor": 1.0
            },

            "regeneracao": {
                "ids": [9],
                "valor": 2.0
            },

            "agricultura": {
                "ids": [14, 15, 18, 19, 20, 39, 40, 41, 36, 46, 47, 48],
                "valor": 3.0
            },

            "urbano": {
                "ids": [22, 23, 24, 25, 30, 26, 31, 33],
                "valor": 4.0
            }
        }

    # DECLIVIDADE

    def _config_declividade(self):

        return [
            {
                "min": 0.0,
                "max": 9.0,
                "valor": 4.0
            },
            {
                "min": 9.0,
                "max": 23.0,
                "valor": 3.0
            },
            {
                "min": 23.0,
                "max": 51.0,
                "valor": 2.0
            },
            {
                "min": 51.0,
                "max": None,
                "valor": 1.0
            }
        ]

    # FLUXO ACUMULADO

    def _config_fluxo(self):

        return [
            {
                "min": 0.0,
                "max": 1600.0,
                "valor": 1.0
            },
            {
                "min": 1601.0,
                "max": 5500.0,
                "valor": 2.0
            },
            {
                "min": 5501.0,
                "max": 18000.0,
                "valor": 3.0
            },
            {
                "min": 18000.0,
                "max": None,
                "valor": 4.0
            }
        ]

    # HIPSOMETRIA

    def _config_hipsometria(self):

        analise = AnaliseHipsometria(
            cidade=self.cidade,
            crs=self.crs
        )

        return analise.gerar_classes()

    # PESOS AHP

    def _config_pesos(self):

        ahp = AHPService()
        pesos, cr = ahp.calcular_pesos()

        return {
            "uso": float(pesos[0]),
            "declividade": float(pesos[1]),
            "fluxo": float(pesos[2]),
            "hipsometria": float(pesos[3]),
        }
