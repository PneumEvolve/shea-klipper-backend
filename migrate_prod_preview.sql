Using database: postgresql+psycopg2://postgres:Coolmints94!@db.marispwfnzezwetzmzdc.supabase.co:5432/postgres?sslmode=require
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> a536bcb27d0f

CREATE TABLE users (
    id SERIAL NOT NULL, 
    email VARCHAR, 
    hashed_password VARCHAR, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_id ON users (id);

CREATE TABLE transcriptions (
    id SERIAL NOT NULL, 
    filename VARCHAR, 
    transcription_text VARCHAR, 
    user_id INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_transcriptions_filename ON transcriptions (filename);

CREATE INDEX ix_transcriptions_id ON transcriptions (id);

INSERT INTO alembic_version (version_num) VALUES ('a536bcb27d0f') RETURNING alembic_version.version_num;

-- Running upgrade a536bcb27d0f -> a2206cd7ae94

ALTER TABLE transcriptions ADD COLUMN summary_text TEXT;

ALTER TABLE transcriptions ALTER COLUMN transcription_text TYPE TEXT;

UPDATE alembic_version SET version_num='a2206cd7ae94' WHERE alembic_version.version_num = 'a536bcb27d0f';

-- Running upgrade a2206cd7ae94 -> ded3ab193ec4

UPDATE alembic_version SET version_num='ded3ab193ec4' WHERE alembic_version.version_num = 'a2206cd7ae94';

-- Running upgrade ded3ab193ec4 -> 337ef47496d9

ALTER TABLE transcriptions ADD COLUMN category VARCHAR;

ALTER TABLE transcriptions DROP CONSTRAINT transcriptions_user_id_fkey;

ALTER TABLE transcriptions ADD FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE;

UPDATE alembic_version SET version_num='337ef47496d9' WHERE alembic_version.version_num = 'ded3ab193ec4';

-- Running upgrade 337ef47496d9 -> d0ae4e650f64

ALTER TABLE transcriptions ADD COLUMN uploaded_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE transcriptions ALTER COLUMN filename SET NOT NULL;

ALTER TABLE transcriptions ALTER COLUMN user_id SET NOT NULL;

DROP INDEX ix_transcriptions_filename;

ALTER TABLE transcriptions DROP CONSTRAINT transcriptions_user_id_fkey;

ALTER TABLE transcriptions ADD FOREIGN KEY(user_id) REFERENCES users (id);

ALTER TABLE transcriptions DROP COLUMN category;

UPDATE alembic_version SET version_num='d0ae4e650f64' WHERE alembic_version.version_num = '337ef47496d9';

-- Running upgrade d0ae4e650f64 -> f98c7289251a

CREATE TABLE food_inventory (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    ingredients TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_food_inventory_id ON food_inventory (id);

CREATE TABLE recipes (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    name VARCHAR NOT NULL, 
    ingredients TEXT NOT NULL, 
    instructions TEXT, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_recipes_id ON recipes (id);

UPDATE alembic_version SET version_num='f98c7289251a' WHERE alembic_version.version_num = 'd0ae4e650f64';

-- Running upgrade f98c7289251a -> 153338a517d2

UPDATE alembic_version SET version_num='153338a517d2' WHERE alembic_version.version_num = 'f98c7289251a';

-- Running upgrade 153338a517d2 -> 618e711e0e7f

UPDATE alembic_version SET version_num='618e711e0e7f' WHERE alembic_version.version_num = '153338a517d2';

-- Running upgrade 618e711e0e7f -> b994319b67ba

UPDATE alembic_version SET version_num='b994319b67ba' WHERE alembic_version.version_num = '618e711e0e7f';

-- Running upgrade b994319b67ba -> 987f540d0deb

CREATE TABLE categories (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    categories TEXT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_categories_id ON categories (id);

UPDATE alembic_version SET version_num='987f540d0deb' WHERE alembic_version.version_num = 'b994319b67ba';

-- Running upgrade 987f540d0deb -> 5caa23cdb3e6

CREATE TABLE user_categories (
    user_id INTEGER NOT NULL, 
    category_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, category_id), 
    FOREIGN KEY(category_id) REFERENCES categories (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

ALTER TABLE categories ADD COLUMN name VARCHAR NOT NULL;

ALTER TABLE categories ADD UNIQUE (name);

ALTER TABLE categories DROP CONSTRAINT categories_user_id_fkey;

ALTER TABLE categories DROP COLUMN categories;

ALTER TABLE categories DROP COLUMN user_id;

ALTER TABLE food_inventory ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE recipes ALTER COLUMN user_id SET NOT NULL;

UPDATE alembic_version SET version_num='5caa23cdb3e6' WHERE alembic_version.version_num = '987f540d0deb';

-- Running upgrade 5caa23cdb3e6 -> af573d1c90e1

UPDATE alembic_version SET version_num='af573d1c90e1' WHERE alembic_version.version_num = '5caa23cdb3e6';

-- Running upgrade af573d1c90e1 -> b20f6d755370

UPDATE alembic_version SET version_num='b20f6d755370' WHERE alembic_version.version_num = 'af573d1c90e1';

-- Running upgrade b20f6d755370 -> 7b0d157cfa62

ALTER TABLE food_inventory ADD COLUMN items TEXT;

ALTER TABLE food_inventory DROP COLUMN ingredients;

UPDATE alembic_version SET version_num='7b0d157cfa62' WHERE alembic_version.version_num = 'b20f6d755370';

-- Running upgrade 7b0d157cfa62 -> 5d5f03092a58

ALTER TABLE food_inventory ADD COLUMN name VARCHAR;

ALTER TABLE food_inventory ADD COLUMN quantity INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE food_inventory ADD COLUMN desired_quantity INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE food_inventory ADD COLUMN categories TEXT;

UPDATE food_inventory SET name = 'Unnamed Item' WHERE name IS NULL;

ALTER TABLE food_inventory ALTER COLUMN name SET NOT NULL;

ALTER TABLE food_inventory DROP COLUMN items;

UPDATE alembic_version SET version_num='5d5f03092a58' WHERE alembic_version.version_num = '7b0d157cfa62';

-- Running upgrade 5d5f03092a58 -> 9504bfe2ba32

ALTER TABLE categories ADD COLUMN type VARCHAR DEFAULT 'food' NOT NULL;

UPDATE alembic_version SET version_num='9504bfe2ba32' WHERE alembic_version.version_num = '5d5f03092a58';

-- Running upgrade 9504bfe2ba32 -> f5436347e963

ALTER TABLE recipes ADD COLUMN category VARCHAR;

UPDATE alembic_version SET version_num='f5436347e963' WHERE alembic_version.version_num = '9504bfe2ba32';

-- Running upgrade f5436347e963 -> 7afe1967630c

CREATE TABLE grocery_lists (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_grocery_lists_id ON grocery_lists (id);

CREATE TABLE grocery_items (
    id SERIAL NOT NULL, 
    list_id INTEGER NOT NULL, 
    name VARCHAR NOT NULL, 
    quantity VARCHAR, 
    have BOOLEAN, 
    note VARCHAR, 
    PRIMARY KEY (id), 
    FOREIGN KEY(list_id) REFERENCES grocery_lists (id)
);

CREATE INDEX ix_grocery_items_id ON grocery_items (id);

UPDATE alembic_version SET version_num='7afe1967630c' WHERE alembic_version.version_num = 'f5436347e963';

-- Running upgrade 7afe1967630c -> a2d29340f613

CREATE TABLE transcription_usage (
    id SERIAL NOT NULL, 
    user_id INTEGER, 
    tokens_used INTEGER, 
    cost_usd FLOAT, 
    timestamp TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_transcription_usage_id ON transcription_usage (id);

UPDATE alembic_version SET version_num='a2d29340f613' WHERE alembic_version.version_num = '7afe1967630c';

-- Running upgrade a2d29340f613 -> 52adac373808

UPDATE alembic_version SET version_num='52adac373808' WHERE alembic_version.version_num = 'a2d29340f613';

-- Running upgrade 52adac373808 -> 2ff15663af35

CREATE TABLE payments (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    amount FLOAT NOT NULL, 
    currency VARCHAR, 
    stripe_session_id VARCHAR NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    UNIQUE (stripe_session_id)
);

CREATE INDEX ix_payments_id ON payments (id);

ALTER TABLE users ADD COLUMN has_active_payment BOOLEAN;

ALTER TABLE users ADD COLUMN api_balance_dollars FLOAT;

UPDATE alembic_version SET version_num='2ff15663af35' WHERE alembic_version.version_num = '52adac373808';

-- Running upgrade 2ff15663af35 -> 079a3a5175c2

UPDATE alembic_version SET version_num='079a3a5175c2' WHERE alembic_version.version_num = '2ff15663af35';

-- Running upgrade 079a3a5175c2 -> 1eb4856b6154

ALTER TABLE transcription_usage ADD COLUMN cost FLOAT;

ALTER TABLE transcription_usage DROP COLUMN cost_usd;

UPDATE alembic_version SET version_num='1eb4856b6154' WHERE alembic_version.version_num = '079a3a5175c2';

-- Running upgrade 1eb4856b6154 -> 3ca896ecb3ca

UPDATE alembic_version SET version_num='3ca896ecb3ca' WHERE alembic_version.version_num = '1eb4856b6154';

-- Running upgrade 3ca896ecb3ca -> 31e4962c6ae1

ALTER TABLE payments ADD COLUMN tokens_purchased INTEGER;

UPDATE alembic_version SET version_num='31e4962c6ae1' WHERE alembic_version.version_num = '3ca896ecb3ca';

-- Running upgrade 31e4962c6ae1 -> 564e566bcf61

CREATE TABLE ramblings (
    id SERIAL NOT NULL, 
    content VARCHAR NOT NULL, 
    tag VARCHAR, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_ramblings_id ON ramblings (id);

UPDATE alembic_version SET version_num='564e566bcf61' WHERE alembic_version.version_num = '31e4962c6ae1';

-- Running upgrade 564e566bcf61 -> 49ad974c558a

ALTER TABLE ramblings ADD COLUMN user_id INTEGER;

ALTER TABLE ramblings ADD FOREIGN KEY(user_id) REFERENCES users (id);

UPDATE alembic_version SET version_num='49ad974c558a' WHERE alembic_version.version_num = '564e566bcf61';

-- Running upgrade 49ad974c558a -> bda12db6ca7a

ALTER TABLE grocery_items ADD COLUMN grocery_list_id INTEGER NOT NULL;

ALTER TABLE grocery_items ADD COLUMN checked BOOLEAN;

ALTER TABLE grocery_items ALTER COLUMN quantity TYPE INTEGER USING quantity::integer;

ALTER TABLE grocery_items DROP CONSTRAINT grocery_items_list_id_fkey;

ALTER TABLE grocery_items ADD FOREIGN KEY(grocery_list_id) REFERENCES grocery_lists (id);

ALTER TABLE grocery_items DROP COLUMN note;

ALTER TABLE grocery_items DROP COLUMN list_id;

ALTER TABLE grocery_items DROP COLUMN have;

UPDATE alembic_version SET version_num='bda12db6ca7a' WHERE alembic_version.version_num = '49ad974c558a';

-- Running upgrade bda12db6ca7a -> 72fa7d762ef0

CREATE TABLE journal_entries (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    title VARCHAR NOT NULL, 
    content TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_journal_entries_id ON journal_entries (id);

UPDATE alembic_version SET version_num='72fa7d762ef0' WHERE alembic_version.version_num = 'bda12db6ca7a';

-- Running upgrade 72fa7d762ef0 -> 45930dbec767

ALTER TABLE journal_entries ADD COLUMN reflection TEXT;

UPDATE alembic_version SET version_num='45930dbec767' WHERE alembic_version.version_num = '72fa7d762ef0';

-- Running upgrade 45930dbec767 -> e14b74cd3d05

ALTER TABLE journal_entries ADD COLUMN mantra TEXT;

ALTER TABLE journal_entries ADD COLUMN next_action TEXT;

UPDATE alembic_version SET version_num='e14b74cd3d05' WHERE alembic_version.version_num = '45930dbec767';

-- Running upgrade e14b74cd3d05 -> dc7a5e0411d6

UPDATE alembic_version SET version_num='dc7a5e0411d6' WHERE alembic_version.version_num = 'e14b74cd3d05';

-- Running upgrade dc7a5e0411d6 -> 2f3dc4a3c4a1

CREATE TABLE threads (
    id SERIAL NOT NULL, 
    text TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    user_id INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_threads_id ON threads (id);

CREATE TABLE comments (
    id SERIAL NOT NULL, 
    text TEXT NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    thread_id INTEGER, 
    user_id INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(thread_id) REFERENCES threads (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='2f3dc4a3c4a1' WHERE alembic_version.version_num = 'dc7a5e0411d6';

-- Running upgrade 2f3dc4a3c4a1 -> 6490910b4ee5

CREATE TABLE we_dream_entries (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    vision TEXT NOT NULL, 
    mantra VARCHAR NOT NULL, 
    is_active INTEGER, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_we_dream_entries_id ON we_dream_entries (id);

UPDATE alembic_version SET version_num='6490910b4ee5' WHERE alembic_version.version_num = '2f3dc4a3c4a1';

-- Running upgrade 6490910b4ee5 -> 7fe73481d8c6

UPDATE alembic_version SET version_num='7fe73481d8c6' WHERE alembic_version.version_num = '6490910b4ee5';

-- Running upgrade 7fe73481d8c6 -> 1f18d9049d4d

UPDATE alembic_version SET version_num='1f18d9049d4d' WHERE alembic_version.version_num = '7fe73481d8c6';

-- Running upgrade 1f18d9049d4d -> c590b05eca0a

CREATE TABLE dream_machine_outputs (
    id SERIAL NOT NULL, 
    summary TEXT NOT NULL, 
    mantra VARCHAR NOT NULL, 
    entry_count INTEGER NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_dream_machine_outputs_id ON dream_machine_outputs (id);

UPDATE alembic_version SET version_num='c590b05eca0a' WHERE alembic_version.version_num = '1f18d9049d4d';

-- Running upgrade c590b05eca0a -> 149d95899fee

CREATE TABLE nodes (
    id SERIAL NOT NULL, 
    name VARCHAR NOT NULL, 
    mission VARCHAR, 
    resources VARCHAR, 
    skills_needed VARCHAR, 
    user_id INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_nodes_id ON nodes (id);

UPDATE alembic_version SET version_num='149d95899fee' WHERE alembic_version.version_num = 'c590b05eca0a';

-- Running upgrade 149d95899fee -> 5e28c20f4e76

CREATE TABLE node_membership (
    user_id INTEGER NOT NULL, 
    node_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, node_id), 
    FOREIGN KEY(node_id) REFERENCES nodes (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

UPDATE alembic_version SET version_num='5e28c20f4e76' WHERE alembic_version.version_num = '149d95899fee';

-- Running upgrade 5e28c20f4e76 -> 089911684901

CREATE TABLE node_membership (
    user_id INTEGER NOT NULL, 
    node_id INTEGER NOT NULL, 
    PRIMARY KEY (user_id, node_id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    FOREIGN KEY(node_id) REFERENCES nodes (id)
);

UPDATE alembic_version SET version_num='089911684901' WHERE alembic_version.version_num = '5e28c20f4e76';

-- Running upgrade 089911684901 -> 805df2c6c1f9

CREATE TABLE gardens (
    id SERIAL NOT NULL, 
    type VARCHAR NOT NULL, 
    host_name VARCHAR NOT NULL, 
    location VARCHAR NOT NULL, 
    description TEXT, 
    notes TEXT, 
    status VARCHAR, 
    created_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id)
);

CREATE INDEX ix_gardens_id ON gardens (id);

CREATE TABLE volunteer_applications (
    id SERIAL NOT NULL, 
    garden_id INTEGER NOT NULL, 
    name VARCHAR NOT NULL, 
    email VARCHAR NOT NULL, 
    message TEXT, 
    approved BOOLEAN, 
    submitted_at TIMESTAMP WITHOUT TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(garden_id) REFERENCES gardens (id)
);

CREATE INDEX ix_volunteer_applications_id ON volunteer_applications (id);

UPDATE alembic_version SET version_num='805df2c6c1f9' WHERE alembic_version.version_num = '089911684901';

-- Running upgrade 805df2c6c1f9 -> b1a2c3d4e5f6

select to_regclass('public.users');

