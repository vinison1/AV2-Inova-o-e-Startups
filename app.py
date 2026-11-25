"""
Suindara - Escolhas mais inteligentes, experiências melhores.

Plataforma de avaliações verificadas para estabelecimentos em geral
(restaurantes, lojas, estacionamentos, clínicas...). Só publica nota e
relato quem comprova a visita com um código único de comprovante/cupom,
que vale uma única vez.

MVP acadêmico: Flask + SQLite + Bootstrap 5.

Como rodar:
    python app.py

Na primeira execução o banco (suindara.db) é criado e populado sozinho.
Para voltar ao estado inicial da demonstração:
    python app.py --reset
"""

import argparse
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "suindara.db")
FORMATO_DB = "%Y-%m-%d %H:%M:%S"

NOME_APP = "Suindara"
SLOGAN = "Escolhas mais inteligentes, experiências melhores."
PROPOSTA = (
    "Avaliações verificadas de estabelecimentos: só avalia quem comprova a "
    "visita com um código único de comprovante."
)
PREFIXO_CODIGO = "SUI"

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SUINDARA_SECRET_KEY", "suindara-chave-local-apenas-para-demonstracao"
)
app.config["TEMPLATES_AUTO_RELOAD"] = True


# ---------------------------------------------------------------------------
# Banco de dados (SQLite)
# ---------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS estabelecimentos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL,
    categoria    TEXT NOT NULL,
    bairro       TEXT NOT NULL,
    endereco     TEXT NOT NULL,
    descricao    TEXT NOT NULL,
    faixa_preco  TEXT NOT NULL,
    emoji        TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    senha_hash   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS codigos_comprovante (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    estabelecimento_id  INTEGER NOT NULL REFERENCES estabelecimentos(id) ON DELETE CASCADE,
    codigo              TEXT NOT NULL UNIQUE,
    usado               INTEGER NOT NULL DEFAULT 0 CHECK (usado IN (0, 1)),
    criado_em           TEXT NOT NULL,
    usado_em            TEXT,
    usado_por           TEXT
);

-- UNIQUE em codigo_id: mesmo que a aplicação falhe, o banco garante que
-- um código de comprovante nunca gere mais de uma avaliação.
CREATE TABLE IF NOT EXISTS avaliacoes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    estabelecimento_id  INTEGER NOT NULL REFERENCES estabelecimentos(id) ON DELETE CASCADE,
    codigo_id           INTEGER NOT NULL UNIQUE REFERENCES codigos_comprovante(id),
    nome_cliente        TEXT NOT NULL,
    nota                INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    comentario          TEXT NOT NULL,
    criado_em           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_avaliacoes_estabelecimento ON avaliacoes(estabelecimento_id);
CREATE INDEX IF NOT EXISTS idx_codigos_estabelecimento ON codigos_comprovante(estabelecimento_id);
"""

# Dados fictícios de demonstração (estabelecimentos de Fortaleza, de nichos
# variados). Cada estabelecimento possui login próprio para acesso ao painel.
DADOS_DEMO = [
    {
        "nome": "Alpendre do Sertão",
        "categoria": "Restaurante",
        "bairro": "Varjota",
        "endereco": "Rua Ana Bilhar, 1255 - Varjota, Fortaleza - CE",
        "faixa_preco": "$$",
        "emoji": "🍲",
        "email": "alpendre@suindara.com.br",
        "senha": "123456",
        "descricao": (
            "Cozinha cearense de verdade: carne de sol na manteiga de garrafa, baião "
            "de dois, peixada e sucos de frutas regionais. Casarão com alpendre e "
            "cheiro de comida de casa."
        ),
        "codigo_pronto": "CUPOM-101",
        "avaliacoes": [
            {
                "codigo": "SUI-4127",
                "cliente": "Letícia Moura",
                "nota": 5,
                "dias_atras": 4,
                "comentario": (
                    "A carne de sol na manteiga de garrafa, com macaxeira frita e baião "
                    "de dois cremoso, estava impecável. Serve bem duas pessoas e o "
                    "ambiente lembra a casa da vovó no interior. Saí de lá já pensando "
                    "na próxima visita."
                ),
            },
            {
                "codigo": "SUI-5530",
                "cliente": "Pedro Henrique Lima",
                "nota": 4,
                "dias_atras": 13,
                "comentario": (
                    "A peixada cearense veio bem temperada, com pirão e arroz branco, e "
                    "o suco de cajá estava geladinho. Estacionar na Varjota à noite é "
                    "complicado, mas a comida compensa. Vale reservar nos fins de semana."
                ),
            },
        ],
    },
    {
        "nome": "Mandacaru Moda & Estilo",
        "categoria": "Loja de roupas",
        "bairro": "Aldeota",
        "endereco": "Av. Santos Dumont, 2020 - Aldeota, Fortaleza - CE",
        "faixa_preco": "$$",
        "emoji": "👗",
        "email": "mandacaru@suindara.com.br",
        "senha": "123456",
        "descricao": (
            "Moda casual com tecidos leves pensados para o clima de Fortaleza: linho, "
            "algodão e viscose. Peças de produção local, ajuste de barra na hora e "
            "provadores amplos."
        ),
        "codigo_pronto": "CUPOM-202",
        "avaliacoes": [
            {
                "codigo": "SUI-6218",
                "cliente": "Fernanda Holanda",
                "nota": 5,
                "dias_atras": 2,
                "comentario": (
                    "Comprei um vestido de linho e a vendedora me ajudou a escolher o "
                    "tamanho certo, sem pressão. O ajuste de barra ficou pronto em uma "
                    "hora, enquanto eu tomava um café ali perto. Tecido fresquinho, "
                    "perfeito para o calor daqui."
                ),
            },
            {
                "codigo": "SUI-7743",
                "cliente": "Rodrigo Sampaio",
                "nota": 4,
                "dias_atras": 8,
                "comentario": (
                    "Boas peças e preço justo pela qualidade. O provador estava bem "
                    "organizado, mas o caixa teve fila na sexta à tarde e só havia uma "
                    "atendente. A troca de tamanho foi tranquila, sem burocracia."
                ),
            },
        ],
    },
    {
        "nome": "Park Iracema Estacionamento",
        "categoria": "Estacionamento rotativo",
        "bairro": "Praia de Iracema",
        "endereco": "Rua dos Tabajaras, 340 - Praia de Iracema, Fortaleza - CE",
        "faixa_preco": "$",
        "emoji": "🅿️",
        "email": "park@suindara.com.br",
        "senha": "123456",
        "descricao": (
            "Estacionamento rotativo coberto e vigiado 24 horas, a poucos passos da "
            "Praia de Iracema. Cobrança por tempo na saída, com Pix ou cartão, e vagas "
            "para motos e bicicletas."
        ),
        "codigo_pronto": "CUPOM-303",
        "avaliacoes": [
            {
                "codigo": "SUI-8091",
                "cliente": "Gustavo Pinheiro",
                "nota": 4,
                "dias_atras": 3,
                "comentario": (
                    "Deixei o carro por três horas num sábado à noite e paguei um valor "
                    "justo. Local coberto, bem iluminado e com manobrista atento. A "
                    "cobrança por Pix na saída foi rápida e sem complicação."
                ),
            },
            {
                "codigo": "SUI-3365",
                "cliente": "Aline Façanha",
                "nota": 3,
                "dias_atras": 10,
                "comentario": (
                    "Seguro e bem localizado, mas a rampa de saída fica congestionada no "
                    "fim da noite e levei uns 15 minutos para sair. O atendente foi "
                    "educado e explicou a tarifa direitinho."
                ),
            },
        ],
    },
    {
        "nome": "Clínica Veterinária Pata Amiga",
        "categoria": "Clínica veterinária",
        "bairro": "Cocó",
        "endereco": "Av. Engenheiro Santana Júnior, 1500 - Cocó, Fortaleza - CE",
        "faixa_preco": "$$",
        "emoji": "🐾",
        "email": "pataamiga@suindara.com.br",
        "senha": "123456",
        "descricao": (
            "Consultas, vacinas e exames para cães e gatos, com veterinários "
            "experientes e salas de espera separadas por espécie. Atendimento com hora "
            "marcada e plantão nos fins de semana."
        ),
        "codigo_pronto": "CUPOM-404",
        "avaliacoes": [
            {
                "codigo": "SUI-2874",
                "cliente": "Juliana Mota",
                "nota": 5,
                "dias_atras": 5,
                "comentario": (
                    "Levei minha cachorra para a vacina anual e a veterinária explicou "
                    "tudo com calma, inclusive o calendário dos próximos reforços. Sala "
                    "de espera tranquila e sem atraso. A Mel saiu abanando o rabo."
                ),
            },
            {
                "codigo": "SUI-9346",
                "cliente": "Marcos Studart",
                "nota": 4,
                "dias_atras": 12,
                "comentario": (
                    "Consulta atenciosa e exames com resultado no mesmo dia. Só achei o "
                    "valor do retorno um pouco alto, mas a equipe passou o orçamento "
                    "antes de qualquer procedimento, o que passa confiança."
                ),
            },
        ],
    },
]


def get_db():
    """Abre (uma vez por requisição) a conexão com o SQLite."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def fechar_db(_erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def agora():
    return datetime.now().strftime(FORMATO_DB)


def popular_banco(db):
    """Insere estabelecimentos, credenciais de acesso, avaliações e códigos."""
    agora_dt = datetime.now()
    criado_codigo_pronto = (agora_dt - timedelta(hours=1)).strftime(FORMATO_DB)

    for dados in DADOS_DEMO:
        cur = db.execute(
            """INSERT INTO estabelecimentos
               (nome, categoria, bairro, endereco, descricao, faixa_preco, emoji, email, senha_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dados["nome"],
                dados["categoria"],
                dados["bairro"],
                dados["endereco"],
                dados["descricao"],
                dados["faixa_preco"],
                dados["emoji"],
                dados["email"].lower(),
                generate_password_hash(dados["senha"]),
            ),
        )
        estabelecimento_id = cur.lastrowid

        for av in dados["avaliacoes"]:
            usado_em_dt = agora_dt - timedelta(days=av["dias_atras"])
            usado_em = usado_em_dt.strftime(FORMATO_DB)
            criado_em = (usado_em_dt - timedelta(hours=6)).strftime(FORMATO_DB)

            cur = db.execute(
                """INSERT INTO codigos_comprovante
                   (estabelecimento_id, codigo, usado, criado_em, usado_em, usado_por)
                   VALUES (?, ?, 1, ?, ?, ?)""",
                (estabelecimento_id, av["codigo"], criado_em, usado_em, av["cliente"]),
            )
            codigo_id = cur.lastrowid

            db.execute(
                """INSERT INTO avaliacoes
                   (estabelecimento_id, codigo_id, nome_cliente, nota, comentario, criado_em)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (estabelecimento_id, codigo_id, av["cliente"], av["nota"], av["comentario"], usado_em),
            )

        db.execute(
            """INSERT INTO codigos_comprovante (estabelecimento_id, codigo, criado_em)
               VALUES (?, ?, ?)""",
            (estabelecimento_id, dados["codigo_pronto"], criado_codigo_pronto),
        )


def banco_precisa_atualizar_schema():
    """Verifica se o arquivo SQLite antigo ainda não possui as colunas de login."""
    if not os.path.exists(DB_PATH):
        return False
    db = sqlite3.connect(DB_PATH)
    try:
        colunas = [
            linha[1]
            for linha in db.execute("PRAGMA table_info(estabelecimentos)").fetchall()
        ]
        return len(colunas) > 0 and "email" not in colunas
    except sqlite3.Error:
        return True
    finally:
        db.close()


def init_db(resetar=False):
    """Cria as tabelas (se não existirem) e popula o banco na primeira execução."""
    if (resetar or banco_precisa_atualizar_schema()) and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    try:
        db.executescript(SCHEMA)
        total = db.execute("SELECT COUNT(*) FROM estabelecimentos").fetchone()[0]
        if total == 0:
            popular_banco(db)
            db.commit()
            print("[Suindara] Banco criado e populado com logins e dados de demonstração.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Consultas, autenticação e regras de negócio
# ---------------------------------------------------------------------------
CONSULTA_ESTABELECIMENTOS = """
    SELECT e.*,
           COUNT(a.id)           AS total_avaliacoes,
           ROUND(AVG(a.nota), 1) AS media
    FROM estabelecimentos e
    LEFT JOIN avaliacoes a ON a.estabelecimento_id = e.id
    {filtro}
    GROUP BY e.id
    ORDER BY e.id
"""


def listar_estabelecimentos(db):
    return db.execute(CONSULTA_ESTABELECIMENTOS.format(filtro="")).fetchall()


def buscar_estabelecimento(db, estabelecimento_id):
    return db.execute(
        CONSULTA_ESTABELECIMENTOS.format(filtro="WHERE e.id = ?"), (estabelecimento_id,)
    ).fetchone()


def login_required(view):
    """Impede que visitantes acessem rotas restritas dos estabelecimentos."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("estabelecimento_id"):
            flash(
                "Acesso restrito: faça login com a conta do estabelecimento para entrar no painel.",
                "warning",
            )
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def para_inteiro(valor, padrao=0):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def normalizar_codigo(texto):
    """Padroniza o que o cliente digitou: ' cupom 101 ' -> 'CUPOM-101'."""
    texto = (texto or "").strip().upper().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "-", texto)


class ErroValidacao(Exception):
    """Erro de validação com mensagem clara para o usuário e o campo envolvido."""

    def __init__(self, mensagem, campo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campo = campo


def publicar_avaliacao(db, estabelecimento_id, nome, codigo_digitado, nota, comentario):
    """Valida o código do comprovante, publica a avaliação e "queima" o código."""
    codigo = normalizar_codigo(codigo_digitado)

    if not nome:
        raise ErroValidacao("Informe seu nome para publicar a avaliação.", "nome")
    if len(nome) > 60:
        raise ErroValidacao("O nome pode ter no máximo 60 caracteres.", "nome")
    if not codigo:
        raise ErroValidacao(
            "Informe o código que está no seu comprovante ou cupom.", "codigo"
        )
    if not 1 <= nota <= 5:
        raise ErroValidacao("Escolha uma nota de 1 a 5 estrelas.", "nota")
    if len(comentario) < 10:
        raise ErroValidacao(
            "Conte um pouco mais sobre sua experiência (mínimo de 10 caracteres).",
            "comentario",
        )
    if len(comentario) > 600:
        raise ErroValidacao("O comentário pode ter no máximo 600 caracteres.", "comentario")

    linha = db.execute(
        "SELECT id, estabelecimento_id, usado FROM codigos_comprovante WHERE codigo = ?",
        (codigo,),
    ).fetchone()

    if linha is None:
        raise ErroValidacao(
            f"O código {codigo} não existe. Confira o código impresso no seu "
            "comprovante ou cupom e tente de novo.",
            "codigo",
        )
    if linha["estabelecimento_id"] != estabelecimento_id:
        raise ErroValidacao(
            f"O código {codigo} foi emitido por outro estabelecimento e não vale "
            "para este local. Avalie o estabelecimento onde você esteve.",
            "codigo",
        )

    mensagem_usado = (
        f"O código {codigo} já foi utilizado. Cada comprovante libera apenas uma avaliação."
    )
    if linha["usado"]:
        raise ErroValidacao(mensagem_usado, "codigo")

    try:
        cur = db.execute(
            """UPDATE codigos_comprovante
               SET usado = 1, usado_em = ?, usado_por = ?
               WHERE id = ? AND usado = 0""",
            (agora(), nome, linha["id"]),
        )
        if cur.rowcount != 1:
            db.rollback()
            raise ErroValidacao(mensagem_usado, "codigo")

        cur = db.execute(
            """INSERT INTO avaliacoes
               (estabelecimento_id, codigo_id, nome_cliente, nota, comentario, criado_em)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (estabelecimento_id, linha["id"], nome, nota, comentario, agora()),
        )
        db.commit()
        return cur.lastrowid
    except sqlite3.Error:
        db.rollback()
        raise ErroValidacao(
            "Não foi possível publicar sua avaliação agora. Tente novamente em instantes."
        )


def criar_codigo(db, estabelecimento_id):
    """Gera um código de comprovante inédito no formato SUI-0000."""
    for _ in range(50):
        codigo = f"{PREFIXO_CODIGO}-{secrets.randbelow(9000) + 1000}"
        try:
            cur = db.execute(
                """INSERT INTO codigos_comprovante (estabelecimento_id, codigo, criado_em)
                   VALUES (?, ?, ?)""",
                (estabelecimento_id, codigo, agora()),
            )
            db.commit()
            return codigo, cur.lastrowid
        except sqlite3.IntegrityError:
            db.rollback()
    raise RuntimeError("Não foi possível gerar um código único.")


# ---------------------------------------------------------------------------
# Filtros e variáveis disponíveis nos templates
# ---------------------------------------------------------------------------
@app.template_filter("data_br")
def filtro_data_br(valor, com_hora=False):
    if not valor:
        return "-"
    momento = datetime.strptime(valor, FORMATO_DB)
    return momento.strftime("%d/%m/%Y às %H:%M" if com_hora else "%d/%m/%Y")


@app.template_filter("decimal_br")
def filtro_decimal_br(valor, casas=1):
    return f"{float(valor):.{casas}f}".replace(".", ",")


@app.context_processor
def variaveis_globais():
    estabelecimento_logado = None
    est_id = session.get("estabelecimento_id")
    if est_id:
        estabelecimento_logado = buscar_estabelecimento(get_db(), est_id)
        if estabelecimento_logado is None:
            session.pop("estabelecimento_id", None)

    return {
        "NOME_APP": NOME_APP,
        "SLOGAN": SLOGAN,
        "PROPOSTA": PROPOSTA,
        "PREFIXO_CODIGO": PREFIXO_CODIGO,
        "ano_atual": datetime.now().year,
        "estabelecimento_logado": estabelecimento_logado,
    }


# ---------------------------------------------------------------------------
# Rotas Públicas (Consumidor)
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Vitrine de estabelecimentos."""
    estabelecimentos = listar_estabelecimentos(get_db())
    return render_template("index.html", estabelecimentos=estabelecimentos)


@app.route("/estabelecimento/<int:estabelecimento_id>", methods=["GET", "POST"])
def estabelecimento(estabelecimento_id):
    """Página do estabelecimento: avaliações verificadas + formulário de nova avaliação."""
    db = get_db()
    est = buscar_estabelecimento(db, estabelecimento_id)
    if est is None:
        abort(404)

    form = {
        "nome": "",
        "codigo": request.args.get("codigo", "").strip()[:30],
        "nota": 0,
        "comentario": "",
    }
    erro = None

    if request.method == "POST":
        form = {
            "nome": request.form.get("nome", "").strip(),
            "codigo": request.form.get("codigo", "").strip(),
            "nota": para_inteiro(request.form.get("nota")),
            "comentario": request.form.get("comentario", "").strip(),
        }
        try:
            avaliacao_id = publicar_avaliacao(
                db,
                est["id"],
                form["nome"],
                form["codigo"],
                form["nota"],
                form["comentario"],
            )
        except ErroValidacao as e:
            erro = e
        else:
            flash(
                f"Avaliação publicada com o selo Visita Verificada. O código "
                f"{normalizar_codigo(form['codigo'])} foi marcado como utilizado e "
                "não pode mais ser reaproveitado.",
                "success",
            )
            return redirect(
                url_for(
                    "estabelecimento",
                    estabelecimento_id=est["id"],
                    nova=avaliacao_id,
                    _anchor="mensagem",
                )
            )

    avaliacoes = db.execute(
        """SELECT id, nome_cliente, nota, comentario, criado_em
           FROM avaliacoes
           WHERE estabelecimento_id = ?
           ORDER BY criado_em DESC, id DESC""",
        (est["id"],),
    ).fetchall()

    html = render_template(
        "estabelecimento.html",
        e=est,
        avaliacoes=avaliacoes,
        form=form,
        erro=erro,
        nova=request.args.get("nova", type=int),
    )
    return html, (400 if erro else 200)


# ---------------------------------------------------------------------------
# Rotas Restritas (Login e Área do Estabelecimento)
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Tela de autenticação exclusiva para estabelecimentos parceiros."""
    if session.get("estabelecimento_id"):
        return redirect(url_for("painel"))

    erro = None
    email_digitado = ""

    if request.method == "POST":
        email_digitado = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        db = get_db()
        est = db.execute(
            "SELECT id, nome, senha_hash FROM estabelecimentos WHERE LOWER(email) = ?",
            (email_digitado,),
        ).fetchone()

        if est and check_password_hash(est["senha_hash"], senha):
            session.clear()
            session["estabelecimento_id"] = est["id"]
            flash(f"Bem-vindo ao painel de {est['nome']}!", "success")
            return redirect(url_for("painel"))

        erro = "E-mail ou senha incorretos. Verifique os dados do estabelecimento."

    return (
        render_template(
            "login.html",
            erro=erro,
            email=email_digitado,
            contas_demo=DADOS_DEMO,
        ),
        (401 if erro else 200),
    )


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Encerra a sessão do estabelecimento."""
    session.clear()
    flash("Você saiu da área do estabelecimento.", "success")
    return redirect(url_for("index"))


@app.route("/painel")
@login_required
def painel():
    """Área restrita do estabelecimento autenticado."""
    db = get_db()
    estabelecimento_id = session["estabelecimento_id"]
    selecionado = buscar_estabelecimento(db, estabelecimento_id)

    if selecionado is None:
        session.clear()
        return redirect(url_for("login"))

    codigos = db.execute(
        "SELECT * FROM codigos_comprovante WHERE estabelecimento_id = ? ORDER BY id DESC",
        (estabelecimento_id,),
    ).fetchall()
    novo_id = request.args.get("novo", type=int)
    novo_codigo = next((c for c in codigos if c["id"] == novo_id), None)

    ativos = sum(1 for c in codigos if not c["usado"])
    return render_template(
        "painel.html",
        estabelecimentos=[selecionado],
        selecionado=selecionado,
        codigos=codigos,
        novo_codigo=novo_codigo,
        total_ativos=ativos,
        total_usados=len(codigos) - ativos,
    )


@app.route("/painel/gerar", methods=["POST"])
@login_required
def gerar_codigo():
    """Gera um novo código único apenas para o estabelecimento logado na sessão."""
    db = get_db()
    estabelecimento_id = session["estabelecimento_id"]
    est = buscar_estabelecimento(db, estabelecimento_id)

    if est is None:
        session.clear()
        return redirect(url_for("login"))

    codigo, codigo_id = criar_codigo(db, est["id"])
    flash(f"Código {codigo} gerado para {est['nome']}. Ele vale uma única avaliação.", "success")
    return redirect(url_for("painel", novo=codigo_id))


@app.errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Suindara - MVP de avaliações verificadas")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="apaga o banco e recria tudo com os dados de demonstração",
    )
    parser.add_argument("--porta", type=int, default=5000, help="porta do servidor (padrão: 5000)")
    parser.add_argument("--debug", action="store_true", help="liga o modo debug do Flask")
    args = parser.parse_args()

    init_db(resetar=args.reset)
    print(f"[Suindara] Abra no navegador: http://127.0.0.1:{args.porta}")
    app.run(host="127.0.0.1", port=args.porta, debug=args.debug)
else:
    init_db()