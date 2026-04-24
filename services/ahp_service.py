import numpy as np



class AHPService:
    def __init__(self):
        pass

    def _pesos_metodo_ahp(self, pairwise):
        A = np.array(pairwise, dtype=float)
        # Autovetor principal
        vals, vecs = np.linalg.eig(A)
        idx = np.argmax(vals.real)
        w = vecs[:, idx].real
        w = w / w.sum()

        # Consistência
        n = A.shape[0]
        lambda_max = vals[idx].real
        CI = (lambda_max - n) / (n - 1)
        RI_table = {1:0.00, 2:0.00, 3:0.58, 4:0.90, 5:1.12, 6:1.24, 7:1.32, 8:1.41, 9:1.45, 10:1.49}
        RI = RI_table.get(n, 0.9)
        CR = CI / RI if RI > 0 else 0.0
        return w, CR

    def calcular_pesos(self):
        uso_vs_declividade = 1/5
        uso_vs_fluxo = 3
        uso_vs_hipsometria = 1/5
        declividade_vs_fluxo = 3
        declividade_vs_hipsometria = 1
        fluxo_vs_hipsometria = 1/5

        A = [
            [1, uso_vs_declividade, uso_vs_fluxo, uso_vs_hipsometria],
            [1/uso_vs_declividade, 1, declividade_vs_fluxo, declividade_vs_hipsometria],
            [1/uso_vs_fluxo, 1/declividade_vs_fluxo, 1, fluxo_vs_hipsometria],
            [1/uso_vs_hipsometria, 1/declividade_vs_hipsometria, 1/fluxo_vs_hipsometria, 1]
        ]

        pesos, CR = self._pesos_metodo_ahp(A)

        return pesos, CR
