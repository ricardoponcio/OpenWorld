"""
Configurações centralizadas para o ecossistema de geração de mapas (Mundo, Continente, Cidade).
Centralizado aqui para que todos os geradores compartilhem das mesmas constantes e seja
mais fácil expandir ou plugar em um JSON no futuro.
"""

CARTOGRAPHER_CONFIG = {
    # Parâmetros Base do Mundo
    "frequencia": 200.0,
    "oitavas": 8,
    "persistencia": 0.5,
    "lacunariedade": 2.1,
    "nivel_mar": 0.35,
    "nivel_montanha": 0.8,
    
    # Parâmetros customizados para o ruído do relevo marinho (bancos de areia)
    "ruido_mar_escala": 80.0,     # Frequência horizontal do ruído
    "ruido_mar_oitavas": 3,       # Complexidade do relevo do mar
    "ruido_mar_amplitude": 0.14,  # Amplitude do relevo do mar
    
    # Parâmetros adicionais expostos para controle total da cartografia
    "ruido_macro_escala": 220.0,  # Escala horizontal do relevo base dos continentes
    "ruido_macro_oitavas": 3,     # Detalhamento tectônico do relevo base
    "ruido_costa_escala": 60.0,   # Escala horizontal das reentrâncias das praias e costões
    "ruido_costa_oitavas": 4,     # Rugosidade/irregularidade local das praias e enseadas

    # Escala geográfica real
    "escala_pixel_area_km2": 250, # Área real representada por pixel de terra firme
    
    # Constantes climáticas
    "clima_damping_termico": 0.4,     # Resfriamento da temperatura por altitude
    "clima_umidade_oceano": 0.8,      # Umidade base do oceano
    "clima_umidade_terra_base": 0.4,  # Umidade base da terra firme
    
    # Ruído de dithering para transição de biomas
    "clima_dithering_escala": 350.0,
    "clima_dithering_temp_amp": 0.10,
    "clima_dithering_umid_amp": 0.10,
    
    # Limiares de classificação de biomas
    "limiar_temp_deserto": 0.6,
    "limiar_umid_deserto": 0.5,
    "limiar_temp_mediterraneo": 0.4,
    "limiar_umid_mediterraneo": 0.5,

    # -------------------------------------------------------------------------
    # Parâmetros de Zoom (ROI Zoom) - Suavização Anti "Papel Amassado"
    # Ajustados para criar um relevo mais amigável, estilo "Google Maps"
    # -------------------------------------------------------------------------
    "zoom_micro_hf_escala": 150.0,    # Aumentado para criar fraturas mais largas, menos ruído branco
    "zoom_micro_hf_oitavas": 2,       # Reduzido de 4 para 2 (menos rugas microscópicas)
    "zoom_micro_mf_escala": 250.0,    # Aumentado para vales e colinas regionais mais extensos
    "zoom_micro_mf_oitavas": 2,       # Reduzido para 2 (suaviza as colinas intermediárias)
    "zoom_micro_hf_peso": 0.20,       # Peso do detalhe fino bastante reduzido (antes 0.60)
    "zoom_micro_mf_peso": 0.80,       # Peso principal nas formas regionais maiores (antes 0.40)
    "zoom_micro_amp_base": 0.024,     # Mantido para leve irregularidade costeira
    "zoom_micro_amp_terra": 0.02,     # Reduzido de 0.056 para 0.02 (terra muito mais plana e suave)

    # -------------------------------------------------------------------------
    # Geração de Cidades (LLM)
    # -------------------------------------------------------------------------
    "cidades_min_por_continente": 3,
    "cidades_max_por_continente": 6
}
