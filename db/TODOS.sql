-- =========================
-- Basis: User & (altes) Todo
-- =========================

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(250) NOT NULL UNIQUE,
    password VARCHAR(250) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE todos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    content VARCHAR(100),
    due DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- =========================
-- Ernährungsplan ERM Tabellen
-- =========================

CREATE TABLE NutzerProfil (
    person_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    gewicht_kg DECIMAL(5,2),
    kalorienbedarf INT,
    CONSTRAINT fk_profil_user
        FOREIGN KEY (person_id) REFERENCES users(id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Effekt (
    effekt_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE Gericht (
    gericht_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE Lebensmittel (
    lebensmittel_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    kalorien_pro_100g DECIMAL(6,2) NOT NULL,
    proteine_pro_100g DECIMAL(6,2) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE Nutzer_Effekt (
    person_id INT NOT NULL,
    effekt_id INT NOT NULL,
    PRIMARY KEY (person_id, effekt_id),
    CONSTRAINT fk_ne_person
        FOREIGN KEY (person_id) REFERENCES NutzerProfil(person_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ne_effekt
        FOREIGN KEY (effekt_id) REFERENCES Effekt(effekt_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Gericht_Effekt (
    gericht_id INT NOT NULL,
    effekt_id INT NOT NULL,
    PRIMARY KEY (gericht_id, effekt_id),
    CONSTRAINT fk_ge_gericht
        FOREIGN KEY (gericht_id) REFERENCES Gericht(gericht_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_ge_effekt
        FOREIGN KEY (effekt_id) REFERENCES Effekt(effekt_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Gericht_Lebensmittel (
    gericht_id INT NOT NULL,
    lebensmittel_id INT NOT NULL,
    menge_gramm DECIMAL(7,2) NOT NULL,
    PRIMARY KEY (gericht_id, lebensmittel_id),
    CONSTRAINT fk_gl_gericht
        FOREIGN KEY (gericht_id) REFERENCES Gericht(gericht_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_gl_lebensmittel
        FOREIGN KEY (lebensmittel_id) REFERENCES Lebensmittel(lebensmittel_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Ernaehrungsplan (
    plan_id INT AUTO_INCREMENT PRIMARY KEY,
    person_id INT NOT NULL,
    gericht_id INT NOT NULL,
    mahlzeit VARCHAR(20) NOT NULL,
    tag VARCHAR(20) NOT NULL,
    von_datum DATE NOT NULL,
    bis_datum DATE NOT NULL,
    CONSTRAINT fk_plan_person
        FOREIGN KEY (person_id) REFERENCES NutzerProfil(person_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_plan_gericht
        FOREIGN KEY (gericht_id) REFERENCES Gericht(gericht_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =========================
-- Beispieldaten
-- =========================

INSERT INTO users (username, password) VALUES
('Ruben', 'pass123'),
('anna', 'pass456');

INSERT INTO todos (user_id, content, due) VALUES
(1, 'Lebensmittel eintragen', '2026-01-10 18:00:00'),
(2, 'Gericht erstellen', '2026-01-11 12:00:00');

INSERT INTO NutzerProfil (person_id, name, gewicht_kg, kalorienbedarf) VALUES
(1, 'Ruben Ball', 75.00, 2600),
(2, 'Anna Muster', 62.00, 2000);

INSERT INTO Effekt (name) VALUES
('Bulk'),
('Cut'),
('Erhaltung'),
('Muskelaufbau'),
('Ausdauer'),
('Gewichtsreduktion'),
('Low-Carb'),
('Vegetarisch'),
('Vegan'),
('High-Protein');

INSERT INTO Gericht (name) VALUES
('Haferflocken Bowl'),
('Reis mit Poulet'),
('Quark mit Beeren'),
('Reis, Broccoli mit Poulet'),
('Protein-Pancakes'),
('Lachs mit Gemüse'),
('Thunfisch-Salat'),
('Gemüse-Pfanne mit Tofu'),
('Griechischer Joghurt mit Nüssen'),
('Avocado-Toast'),
('Protein-Shake'),
('Hühnchen-Curry'),
('Quinoa-Bowl'),
('Omelett mit Gemüse');

INSERT INTO Lebensmittel (name, kalorien_pro_100g, proteine_pro_100g) VALUES
('Haferflocken', 370.00, 13.00),
('Banane', 89.00, 1.10),
('Reis', 130.00, 2.70),
('Poulet', 165.00, 31.00),
('Magerquark', 68.00, 12.00),
('Beeren', 50.00, 1.00),
('Eier', 155.00, 13.00),
('Lachs', 208.00, 20.00),
('Mandeln', 579.00, 21.00),
('Avocado', 160.00, 2.00),
('Thunfisch', 132.00, 23.00),
('Tofu', 145.00, 15.00),
('Quinoa', 120.00, 4.40),
('Joghurt griechisch', 97.00, 9.00),
('Süsskartoffel', 86.00, 1.60),
('Spinat', 23.00, 2.90),
('Broccoli', 34.00, 2.80),
('Tomaten', 18.00, 0.90),
('Eiweisspulver', 380.00, 80.00),
('Olivenöl', 884.00, 0.00);

INSERT INTO Nutzer_Effekt (person_id, effekt_id) VALUES
(1, 1),
(2, 2);

INSERT INTO Gericht_Effekt (gericht_id, effekt_id) VALUES
(1, 1),
(2, 1),
(3, 2),
(5, 1),
(5, 10),
(6, 1),
(6, 4),
(7, 2),
(7, 10),
(8, 8),
(8, 9),
(9, 2),
(9, 10);

INSERT INTO Gericht_Lebensmittel (gericht_id, lebensmittel_id, m_
