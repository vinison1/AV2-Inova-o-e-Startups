# Suindara

> Escolhas mais inteligentes, experiências melhores.

MVP web de uma plataforma de avaliações verificadas para **estabelecimentos em geral** (restaurantes, lojas, estacionamentos, clínicas e serviços) em que **só publica nota e relato quem comprova a visita**, usando um **código único de comprovante/cupom, de uso único**.

## A ideia

Avaliações online sofrem com notas falsas, sabotagem de concorrentes e avaliações compradas. A **Suindara** ataca a raiz do problema: sem comprovação de visita, não há avaliação.

1. O **estabelecimento acessa seu painel restrito** (protegido por login) e **gera um código** de comprovante para o cliente (ex.: `SUI-9182`).
2. O **cliente recebe o código no cupom/recibo** e ele só vale para aquele estabelecimento.
3. Ao avaliar, o código é validado e **"queimado"**: não pode ser reutilizado. Cada avaliação publicada recebe o selo verde **Visita Verificada**.

## Tecnologias

| Camada | Tecnologia |
| --- | --- |
| Backend | Python 3.9+ com Flask e Werkzeug (hash de senhas e sessões) |
| Banco de dados | SQLite (arquivo local `suindara.db`, criado automaticamente) |
| Frontend | HTML5, CSS3 e Bootstrap 5 via CDN (com plano B offline) |

## Estrutura de pastas

```text
suindara/
├── app.py                      # Backend Flask, autenticação, banco SQLite e regras de negócio
├── requirements.txt            # Dependências Python
├── README.md
├── templates/
│   ├── base.html               # Layout: navbar dinâmica, rodapé, Bootstrap
│   ├── _macros.html            # Componentes: coruja, selo, badge, estrelas, mensagens
│   ├── index.html              # Vitrine pública de estabelecimentos
│   ├── estabelecimento.html    # Avaliações verificadas + formulário de avaliação
│   ├── login.html              # Acesso restrito do estabelecimento
│   ├── painel.html             # Área do Estabelecimento (gerador de códigos únicos)
│   └── 404.html
└── static/
    └── css/
        └── style.css           # Identidade visual Suindara (#3F6C45, #232524, #DCE0DD, #4B9A54)
```

O arquivo `suindara.db` é gerado automaticamente na primeira execução.

## Como instalar e rodar

```bash
# 1. Entre na pasta do projeto
cd suindara

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Rode o servidor local
python app.py
```

Abra **http://127.0.0.1:5000** (ou **http://localhost:5000**) no navegador.

Opções úteis do `app.py`:

| Comando | O que faz |
| --- | --- |
| `python app.py --reset` | Apaga o banco `suindara.db` e recria tudo com os dados e logins iniciais |
| `python app.py --porta 5001` | Roda em outra porta |
| `python app.py --debug` | Liga o modo debug do Flask |

## Dados de demonstração

Estabelecimentos **fictícios** de Fortaleza de diferentes segmentos, cada um com login próprio para acessar o painel, 2 avaliações verificadas e 1 código pronto para uso imediato:

| Estabelecimento | Categoria | Bairro | E-mail de acesso | Senha | Código pronto |
| --- | --- | --- | --- | --- | --- |
| Alpendre do Sertão | Restaurante | Varjota | `alpendre@suindara.com.br` | `123456` | `CUPOM-101` |
| Mandacaru Moda & Estilo | Loja de roupas | Aldeota | `mandacaru@suindara.com.br` | `123456` | `CUPOM-202` |
| Park Iracema Estacionamento | Estacionamento rotativo | Praia de Iracema | `park@suindara.com.br` | `123456` | `CUPOM-303` |
| Clínica Veterinária Pata Amiga | Clínica veterinária | Cocó | `pataamiga@suindara.com.br` | `123456` | `CUPOM-404` |

---

Suindara — Escolhas mais inteligentes, experiências melhores.