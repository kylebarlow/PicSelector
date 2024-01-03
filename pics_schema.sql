--
-- PostgreSQL database dump
--

-- Dumped from database version 15.5 (Debian 15.5-1.pgdg120+1)
-- Dumped by pg_dump version 15.5 (Debian 15.5-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.votes DROP CONSTRAINT IF EXISTS votes_users_id_fk;
ALTER TABLE IF EXISTS ONLY public.votes DROP CONSTRAINT IF EXISTS votes_media_id_fk;
ALTER TABLE IF EXISTS ONLY public.videos DROP CONSTRAINT IF EXISTS videos_media_id_fk;
ALTER TABLE IF EXISTS ONLY public.user_roles DROP CONSTRAINT IF EXISTS user_roles_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.user_roles DROP CONSTRAINT IF EXISTS user_roles_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.thumbnail DROP CONSTRAINT IF EXISTS thumbnail_media_id_fk;
ALTER TABLE IF EXISTS ONLY public.keys DROP CONSTRAINT IF EXISTS keys_media_id_fk;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_media_id_fk;
DROP INDEX IF EXISTS public.thumbnail_id_uindex;
DROP INDEX IF EXISTS public.media_sha256_hash_uindex;
DROP INDEX IF EXISTS public.media_id_uindex;
DROP INDEX IF EXISTS public.creation_time__index;
ALTER TABLE IF EXISTS ONLY public.votes DROP CONSTRAINT IF EXISTS votes_pk;
ALTER TABLE IF EXISTS ONLY public.videos DROP CONSTRAINT IF EXISTS videos_pk;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_username_key;
ALTER TABLE IF EXISTS ONLY public.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY public.user_roles DROP CONSTRAINT IF EXISTS user_roles_pkey;
ALTER TABLE IF EXISTS ONLY public.thumbnail DROP CONSTRAINT IF EXISTS thumbnail_pk;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_pkey;
ALTER TABLE IF EXISTS ONLY public.roles DROP CONSTRAINT IF EXISTS roles_name_key;
ALTER TABLE IF EXISTS ONLY public.media DROP CONSTRAINT IF EXISTS media_pk;
ALTER TABLE IF EXISTS ONLY public.keys DROP CONSTRAINT IF EXISTS keys_pk;
ALTER TABLE IF EXISTS ONLY public.images DROP CONSTRAINT IF EXISTS images_pk;
ALTER TABLE IF EXISTS public.users ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.user_roles ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.thumbnail ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.roles ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.media ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.keys ALTER COLUMN key_id DROP DEFAULT;
DROP TABLE IF EXISTS public.votes;
DROP TABLE IF EXISTS public.videos;
DROP SEQUENCE IF EXISTS public.users_id_seq;
DROP TABLE IF EXISTS public.users;
DROP SEQUENCE IF EXISTS public.user_roles_id_seq;
DROP TABLE IF EXISTS public.user_roles;
DROP SEQUENCE IF EXISTS public.thumbnail_id_seq;
DROP TABLE IF EXISTS public.thumbnail;
DROP SEQUENCE IF EXISTS public.roles_id_seq;
DROP TABLE IF EXISTS public.roles;
DROP SEQUENCE IF EXISTS public.media_id_seq;
DROP TABLE IF EXISTS public.media;
DROP SEQUENCE IF EXISTS public.keys_key_id_seq;
DROP TABLE IF EXISTS public.keys;
DROP TABLE IF EXISTS public.images;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: images; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.images (
    id integer NOT NULL,
    average_hash1 character varying(4) NOT NULL,
    average_hash2 character varying(4) NOT NULL,
    average_hash3 character varying(4) NOT NULL,
    average_hash4 character varying(4) NOT NULL,
    difference_hash1 character varying(4) NOT NULL,
    difference_hash2 character varying(4) NOT NULL,
    difference_hash3 character varying(4) NOT NULL,
    difference_hash4 character varying(4) NOT NULL,
    perceptual_hash1 character varying(4) NOT NULL,
    perceptual_hash2 character varying(4) NOT NULL,
    perceptual_hash3 character varying(4) NOT NULL,
    perceptual_hash4 character varying(4) NOT NULL
);


ALTER TABLE public.images OWNER TO pics;

--
-- Name: keys; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.keys (
    key_id integer NOT NULL,
    media_id integer NOT NULL,
    key character varying NOT NULL
);


ALTER TABLE public.keys OWNER TO pics;

--
-- Name: keys_key_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.keys_key_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.keys_key_id_seq OWNER TO pics;

--
-- Name: keys_key_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.keys_key_id_seq OWNED BY public.keys.key_id;


--
-- Name: media; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.media (
    id integer NOT NULL,
    sha256_hash bytea NOT NULL,
    creation_time timestamp with time zone,
    media_type smallint NOT NULL,
    file_size bigint NOT NULL,
    height integer NOT NULL,
    width integer NOT NULL,
    latitude double precision,
    longitude double precision,
    s3_key character varying,
    utc_time boolean
);


ALTER TABLE public.media OWNER TO pics;

--
-- Name: media_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.media_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.media_id_seq OWNER TO pics;

--
-- Name: media_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.media_id_seq OWNED BY public.media.id;


--
-- Name: roles; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    name character varying(50)
);


ALTER TABLE public.roles OWNER TO pics;

--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.roles_id_seq OWNER TO pics;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;


--
-- Name: thumbnail; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.thumbnail (
    id integer NOT NULL,
    media_id integer,
    key character varying,
    height integer,
    width integer,
    file_size integer
);


ALTER TABLE public.thumbnail OWNER TO pics;

--
-- Name: thumbnail_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.thumbnail_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.thumbnail_id_seq OWNER TO pics;

--
-- Name: thumbnail_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.thumbnail_id_seq OWNED BY public.thumbnail.id;


--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.user_roles (
    id integer NOT NULL,
    user_id integer,
    role_id integer
);


ALTER TABLE public.user_roles OWNER TO pics;

--
-- Name: user_roles_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.user_roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_roles_id_seq OWNER TO pics;

--
-- Name: user_roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.user_roles_id_seq OWNED BY public.user_roles.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.users (
    id integer NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    username character varying(100) NOT NULL,
    password character varying(255) DEFAULT ''::character varying NOT NULL,
    email_confirmed_at timestamp without time zone,
    email character varying(100) DEFAULT ''::character varying NOT NULL,
    first_name character varying(100) DEFAULT ''::character varying NOT NULL,
    last_name character varying(100) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.users OWNER TO pics;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: pics
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.users_id_seq OWNER TO pics;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: pics
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: videos; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.videos (
    id integer NOT NULL,
    duration real NOT NULL,
    original_key character varying
);


ALTER TABLE public.videos OWNER TO pics;

--
-- Name: votes; Type: TABLE; Schema: public; Owner: pics
--

CREATE TABLE public.votes (
    user_id integer,
    media_id integer,
    vote_value smallint
);


ALTER TABLE public.votes OWNER TO pics;

--
-- Name: keys key_id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.keys ALTER COLUMN key_id SET DEFAULT nextval('public.keys_key_id_seq'::regclass);


--
-- Name: media id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.media ALTER COLUMN id SET DEFAULT nextval('public.media_id_seq'::regclass);


--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);


--
-- Name: thumbnail id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.thumbnail ALTER COLUMN id SET DEFAULT nextval('public.thumbnail_id_seq'::regclass);


--
-- Name: user_roles id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.user_roles ALTER COLUMN id SET DEFAULT nextval('public.user_roles_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: images images_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_pk PRIMARY KEY (id);


--
-- Name: keys keys_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.keys
    ADD CONSTRAINT keys_pk PRIMARY KEY (key_id);


--
-- Name: media media_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.media
    ADD CONSTRAINT media_pk PRIMARY KEY (id);


--
-- Name: roles roles_name_key; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_name_key UNIQUE (name);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: thumbnail thumbnail_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.thumbnail
    ADD CONSTRAINT thumbnail_pk PRIMARY KEY (id);


--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: videos videos_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_pk PRIMARY KEY (id);


--
-- Name: votes votes_pk; Type: CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_pk UNIQUE (user_id, media_id);


--
-- Name: creation_time__index; Type: INDEX; Schema: public; Owner: pics
--

CREATE INDEX creation_time__index ON public.media USING btree (creation_time DESC);


--
-- Name: media_id_uindex; Type: INDEX; Schema: public; Owner: pics
--

CREATE UNIQUE INDEX media_id_uindex ON public.media USING btree (id);


--
-- Name: media_sha256_hash_uindex; Type: INDEX; Schema: public; Owner: pics
--

CREATE UNIQUE INDEX media_sha256_hash_uindex ON public.media USING btree (sha256_hash);


--
-- Name: thumbnail_id_uindex; Type: INDEX; Schema: public; Owner: pics
--

CREATE UNIQUE INDEX thumbnail_id_uindex ON public.thumbnail USING btree (id);


--
-- Name: images images_media_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.images
    ADD CONSTRAINT images_media_id_fk FOREIGN KEY (id) REFERENCES public.media(id);


--
-- Name: keys keys_media_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.keys
    ADD CONSTRAINT keys_media_id_fk FOREIGN KEY (media_id) REFERENCES public.media(id);


--
-- Name: thumbnail thumbnail_media_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.thumbnail
    ADD CONSTRAINT thumbnail_media_id_fk FOREIGN KEY (media_id) REFERENCES public.media(id);


--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;


--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: videos videos_media_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.videos
    ADD CONSTRAINT videos_media_id_fk FOREIGN KEY (id) REFERENCES public.media(id);


--
-- Name: votes votes_media_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_media_id_fk FOREIGN KEY (media_id) REFERENCES public.media(id);


--
-- Name: votes votes_users_id_fk; Type: FK CONSTRAINT; Schema: public; Owner: pics
--

ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- PostgreSQL database dump complete
--

