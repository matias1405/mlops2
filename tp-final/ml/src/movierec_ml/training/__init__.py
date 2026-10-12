"""Entrenamiento de la red multi-task que aprende embeddings de películas.

Pretext task supervisado: predecir géneros (multi-label) e idioma original (multi-clase) desde
el texto. Las cabezas se descartan; la salida del tronco compartido es el embedding de la película.
"""
