// TMDB entrega los géneros en inglés: es un conjunto cerrado, así que se traducen en el cliente.
const ES: Record<string, string> = {
  Action: "Acción", Adventure: "Aventura", Animation: "Animación", Comedy: "Comedia", Crime: "Crimen",
  Documentary: "Documental", Drama: "Drama", Family: "Familia", Fantasy: "Fantasía", History: "Historia",
  Horror: "Terror", Music: "Música", Mystery: "Misterio", Romance: "Romance", "Science Fiction": "Ciencia ficción",
  "TV Movie": "Película de TV", Thriller: "Suspenso", War: "Bélica", Western: "Western",
};

export const genreEs = (genre: string): string => ES[genre] ?? genre;
