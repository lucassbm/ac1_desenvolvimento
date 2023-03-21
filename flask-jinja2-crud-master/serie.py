from flask import Flask, make_response, request, render_template, redirect, send_from_directory
from contextlib import closing
import sqlite3
import os
import werkzeug

# Observação: O código abaixo não contém uma estrutura dividida em camadas com blueprints, services, controllers, DAOs, models, etc., pois a ideia é tentar manter tudo bem simples.
#             Quando você estiver trabalhando em seu projeto real, tente separar isso tudo.
#             E idealmente num projeto grande, você teria um serviço fornecendo dados em formato JSON e alguma outra coisa utilizando-os para gerar o HTML, mas aqui está tudo numa coisa só.

############################
#### Definições da API. ####
############################

# Cria o objeto principal do Flask.
app = Flask(__name__)

# Quase todos os métodos terão estas três linhas para se certificar de que o login é válido. Se não for, o usuário será redirecionado para a tela de login.
#   logado = autenticar_login()
#   if logado is None:
#       return redirect("/")
#
# Esse código é bastante repetitivo, o que é bem chato. Até é possível resolver isso movendo-o para method decorators e/ou filtros, no entanto, para não complicarmos demais, vamos deixá-lo assim.

# Os métodos desta camada tem que ser idealmente um tanto "burros". Eles APENAS devem fazer o seguinte e nada mais:
# 1. Autenticação.
# 2. Retirar os dados relevantes da requisição.
# 3. Chamar alguma função no banco de dados ou na regra de negócio que faz o trabalho pesado.
# 4. Montar uma resposta à requisição.

# É importante notar-se que não devem haver regras de negócio aqui.
# Todo o trabalho que essas funções executam deve ser APENAS o de ler a requisição e escrever a resposta, delegando o trabalho de processamento às regras de negócio.

### Partes de login. ###

@app.route("/")
@app.route("/login")
def menu():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return render_template("/login.html", erro = "")

    # Monta a resposta.
    return render_template("menu.html", logado = logado, mensagem = "")

@app.route("/login", methods = ["POST"])
def login():
    # Extrai os dados do formulário.
    f = request.form
    if "login" not in f or "senha" not in f:
        return ":(", 422
    login = f["login"]
    senha = f["senha"]

    # Faz o processamento.
    logado = db_fazer_login(login, senha)

    # Monta a resposta.
    if logado is None:
        return render_template("login.html", erro = "Ops. A senha estava errada.")
    resposta = make_response(redirect("/"))

    # Armazena o login realizado com sucesso em cookies (autenticação).
    resposta.set_cookie("login", login, samesite = "Strict")
    resposta.set_cookie("senha", senha, samesite = "Strict")
    return resposta

@app.route("/logout", methods = ["POST"])
def logout():
    # Monta a resposta.
    resposta = make_response(render_template("login.html", mensagem = "Tchau."))

    # Limpa os cookies com os dados de login (autenticação).
    resposta.set_cookie("login", "", samesite = "Strict")
    resposta.set_cookie("senha", "", samesite = "Strict")
    return resposta

### Cadastro de séries. ###

# Tela de listagem de séries.
@app.route("/feira")
def listar_feiras_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    lista = db_listar_feiras()

    # Monta a resposta.
    return render_template("lista_feiras.html", logado = logado, feiras = lista)

# Tela com o formulário de criação de séries.
@app.route("/feira/novo", methods = ["GET"])
def form_criar_feira_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Monta a resposta.
    return render_template("form_feira.html", logado = logado)

# Processa o formulário de criação de séries.
@app.route("/feira/novo", methods = ["POST"])
def criar_feira_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Extrai os dados do formulário.
    bairro = request.form["bairro"]

    # Faz o processamento.
    ja_existia, feira = criar_feira(bairro)

    # Monta a resposta.
    mensagem = f"A feira do bairro {bairro} já existia com o id {feira['id_feira']}." if ja_existia else f"A feira do bairro {bairro} foi criada com id {feira['id_feira']}."
    return render_template("menu.html", logado = logado, mensagem = mensagem)

### Cadastro de alunos. ###

# Tela de listagem de alunos.
@app.route("/feirante")
def listar_feirantes_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    lista = db_listar_feirantes()

    # Monta a resposta.
    return render_template("lista_feirantes.html", logado = logado, feirantes = lista)

# Tela com o formulário de criação de um novo aluno.
@app.route("/feirante/novo", methods = ["GET"])
def form_criar_feirante_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    lista = db_listar_feiras_ordem()
    feirante = {'id_feirante': 'novo', 'nome': '', 'barraca': '', 'sexo': '', 'id_feira': '', 'id_foto': ''}

    # Monta a resposta.
    return render_template("form_feirante.html", logado = logado, feirante = feirante, feiras = lista)

# Tela com o formulário de alteração de um aluno existente.
@app.route("/feirante/<int:id_feirante>", methods = ["GET"])
def form_alterar_feirante_api(id_feirante):
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    feirante = db_consultar_feirante(id_feirante)
    feiras = db_listar_feiras_ordem()

    # Monta a resposta.
    if feirante is None:
        return render_template("menu.html", logado = logado, mensagem = f"Esse feirante não existe."), 404
    return render_template("form_feirante.html", logado = logado, feirante = feirante, feiras = feiras)

# Processa o formulário de criação de alunos. Inclui upload de fotos.
@app.route("/feirante/novo", methods = ["POST"])
def criar_feirante_api():
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Extrai os dados do formulário.
    nome = request.form["nome"]
    sexo = request.form["sexo"]
    barraca = request.form["barraca"]
    id_feira = request.form["id_feira"]

    # Faz o processamento.
    feirante = criar_feirante(nome, barraca, sexo, id_feira, salvar_arquivo_upload)

    # Monta a resposta.
    mensagem = f"O feirante {nome} foi criado com o id {feirante['id_feirante']}." if sexo == "M" else f"A feirante {nome} foi criada com o id {feirante['id_feirante']}."
    return render_template("menu.html", logado = logado, mensagem = mensagem)

# Processa o formulário de alteração de alunos. Inclui upload de fotos.
@app.route("/feirante/<int:id_feirante>", methods = ["POST"])
def editar_feirante_api(id_feirante):
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Extrai os dados do formulário.
    nome = request.form["nome"]
    sexo = request.form["sexo"]
    barraca = request.form["barraca"]
    id_feira = request.form["id_feira"]

    # Faz o processamento.
    status, feirante = editar_feirante(id_feirante, nome, barraca, sexo, id_feira, salvar_arquivo_upload, deletar_foto)

    # Monta a resposta.
    if status == 'não existe':
        mensagem = "Esse feirante nem mesmo existia mais." if sexo == "M" else "Essa feirante nem mesmo existia mais."
        return render_template("menu.html", logado = logado, mensagem = mensagem), 404
    mensagem = f"O feirante {nome} com o id {id_feirante} foi editado." if sexo == "M" else f"A feirante {nome} com o id {id_feirante} foi editada."
    return render_template("menu.html", logado = logado, mensagem = mensagem)

# Processa o botão de excluir um aluno.
@app.route("/feirante/<int:id_feirante>", methods = ["DELETE"])
def deletar_feirante_api(id_feirante):
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    feirante = apagar_feirante(id_feirante)

    # Monta a resposta.
    if feirante is None:
        return render_template("menu.html", logado = logado, mensagem = "Esse feirante nem mesmo existia mais."), 404
    mensagem = f"O feirante com o id {id_feirante} foi excluído." if feirante['sexo'] == "M" else f"A feirante com o id {id_feirante} foi excluída."
    return render_template("menu.html", logado = logado, mensagem = mensagem)

### Fotos dos alunos. ###

# Faz o download de uma foto.
@app.route("/feirante/foto/<id_foto>")
def feirante_download_foto(id_foto):
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Monta a resposta.
    try:
        return send_from_directory("feirantes_fotos", id_foto)
    except werkzeug.exceptions.NotFound as x:
        return send_from_directory("static", "no-photo.png")

# Deleta uma foto.
@app.route("/feirante/foto/<id_foto>", methods = ["DELETE"])
def feirante_deletar_foto(id_foto):
    # Autenticação.
    logado = autenticar_login()
    if logado is None:
        return redirect("/")

    # Faz o processamento.
    deletar_foto(id_foto)

    # Monta a resposta.
    return ""

###############################################
#### Coisas internas da controller da API. ####
###############################################

def extensao_arquivo(filename):
    if '.' not in filename: return ''
    return filename.rsplit('.', 1)[1].lower()

def salvar_arquivo_upload():
    import uuid
    if "foto" in request.files:
        foto = request.files["foto"]
        e = extensao_arquivo(foto.filename)
        if e in ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp']:
            u = uuid.uuid1()
            n = f"{u}.{e}"
            foto.save(os.path.join("feirantes_fotos", n))
            return n
    return ""

def deletar_foto(id_foto):
    if id_foto == '': return
    p = os.path.join("feirantes_fotos", id_foto)
    if os.path.exists(p):
        os.remove(p)

def autenticar_login():
    login = request.cookies.get("login", "")
    senha = request.cookies.get("senha", "")
    return db_fazer_login(login, senha)

##########################################
#### Definições de regras de negócio. ####
##########################################

def criar_feira(bairro):
    feira_ja_existe = db_verificar_feira(bairro)
    if feira_ja_existe is not None: return True, feira_ja_existe
    feira_nova = db_criar_feira(bairro)
    return False, feira_nova

def criar_feirante(nome, barraca, sexo, id_feira, salvar_foto):
    return db_criar_feirante(nome, barraca, sexo, id_feira, salvar_foto())

def editar_feirante(id_feirante, nome, barraca, sexo, id_feira, salvar_foto, apagar_foto):
    feirante = db_consultar_feirante(id_feirante)
    if feirante is None:
        return 'não existe', None
    id_foto = salvar_foto()
    if id_foto == "":
        id_foto = feirante["id_foto"]
    else:
        apagar_foto(feirante["id_foto"])
    db_editar_feirante(id_feirante, nome, barraca, sexo, id_feira, id_foto)
    return 'alterado', feirante

def apagar_feirante(id_feirante):
    feirante = db_consultar_feirante(id_feirante)
    if feirante is not None: db_deletar_feirante(id_feirante)
    return feirante

###############################################
#### Funções auxiliares de banco de dados. ####
###############################################

# Converte uma linha em um dicionário.
def row_to_dict(description, row):
    if row is None: return None
    d = {}
    for i in range(0, len(row)):
        d[description[i][0]] = row[i]
    return d

# Converte uma lista de linhas em um lista de dicionários.
def rows_to_dict(description, rows):
    result = []
    for row in rows:
        result.append(row_to_dict(description, row))
    return result

####################################
#### Definições básicas de DAO. ####
####################################

sql_create ="""
CREATE TABLE IF NOT EXISTS feira (
    id_feira INTEGER PRIMARY KEY AUTOINCREMENT,
    bairro VARCHAR(50) NOT NULL,
    UNIQUE(bairro)
);

CREATE TABLE IF NOT EXISTS feirante (
    id_feirante INTEGER PRIMARY KEY AUTOINCREMENT,
    nome VARCHAR(50) NOT NULL,
    barraca VARCHAR(50) NOT NULL,
    sexo VARCHAR(1) NOT NULL,
    id_feira INTEGER NOT NULL,
    id_foto VARCHAR(50) NOT NULL,
    FOREIGN KEY(id_feira) REFERENCES feira(id_feira)
);

CREATE TABLE IF NOT EXISTS usuario (
    login VARCHAR(50) PRIMARY KEY NOT NULL,
    senha VARCHAR(50) NOT NULL,
    nome VARCHAR(50) NOT NULL,
    FOREIGN KEY(login) REFERENCES serie(login)
);

REPLACE INTO usuario (login, senha, nome) VALUES ('ironman', 'ferro', 'Tony Stark');
REPLACE INTO usuario (login, senha, nome) VALUES ('spiderman', 'aranha', 'Peter Park');
REPLACE INTO usuario (login, senha, nome) VALUES ('batman', 'morcego', 'Bruce Wayne');
"""

# Observação: A tabela "usuario" acima não utiliza uma forma segura de se armazenar senhas. Isso será abordado mais para frente!

# Observação: Os métodos do DAO devem ser "burros". Eles apenas executam alguma instrução no banco de dados e nada mais.
#             Não devem ter inteligência, pois qualquer tipo de inteligência provavelmente trata-se de uma regra de negócio, e que portanto não deve ficar no DAO.

def conectar():
    return sqlite3.connect('serie.db')

def db_inicializar():
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.executescript(sql_create)
        con.commit()

def db_listar_feiras():
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT id_feira, bairro FROM feira")
        return rows_to_dict(cur.description, cur.fetchall())

def db_listar_feiras_ordem():
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT id_feira, bairro FROM feira ORDER BY bairro")
        return rows_to_dict(cur.description, cur.fetchall())

def db_verificar_feira(bairro):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT id_feira, bairro FROM feira WHERE bairro = ? ", [bairro])
        return row_to_dict(cur.description, cur.fetchone())

def db_consultar_feirante(id_feirante):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT fe.id_feirante, fe.nome, fe.barraca, fe.sexo, fe.id_feira, fe.id_foto, f.bairro FROM feirante fe INNER JOIN feira f ON fe.id_feira = f.id_feira WHERE fe.id_feirante = ?", [id_feirante])
        return row_to_dict(cur.description, cur.fetchone())

def db_listar_feirantes():
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT fe.id_feirante, fe.nome, fe.barraca, fe.sexo, fe.id_feira, fe.id_foto, f.bairro FROM feirante fe INNER JOIN feira f ON fe.id_feira = f.id_feira")
        return rows_to_dict(cur.description, cur.fetchall())

def db_criar_feira(bairro):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("INSERT INTO feira (bairro) VALUES (?)", [bairro])
        id_feira = cur.lastrowid
        con.commit()
        return {'id_feira': id_feira, 'bairro': bairro}

def db_criar_feirante(nome, barraca, sexo, id_feira, id_foto):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("INSERT INTO feirante (nome, barraca, sexo, id_feira, id_foto) VALUES (?, ?, ?, ?, ?)", [nome, barraca, sexo, id_feira, id_foto])
        id_feirante = cur.lastrowid
        con.commit()
        return {'id_feirante': id_feirante, 'nome': nome, 'barraca': barraca, 'sexo': sexo, 'id_feira': id_feira, 'id_foto': id_foto}

def db_editar_feirante(id_feirante, nome, barraca, sexo, id_feira, id_foto):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("UPDATE feirante SET nome = ?, barraca = ?, sexo = ?, id_feira = ?, id_foto = ? WHERE id_feirante = ?", [nome, barraca, sexo, id_feira, id_foto, id_feirante])
        con.commit()
        return {'id_feirante': id_feirante, 'nome': nome, 'barraca': barraca, 'sexo': sexo, 'id_feira': id_feira, 'id_foto': id_foto}

def db_deletar_feirante(id_feirante):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("DELETE FROM feirante WHERE id_feirante = ?", [id_feirante])
        con.commit()

def db_fazer_login(login, senha):
    with closing(conectar()) as con, closing(con.cursor()) as cur:
        cur.execute("SELECT u.login, u.senha, u.nome FROM usuario u WHERE u.login = ? AND u.senha = ?", [login, senha])
        return row_to_dict(cur.description, cur.fetchone())
    

########################
#### Inicialização. ####
########################

if __name__ == "__main__":
    db_inicializar()
    app.run()