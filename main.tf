provider "aws" {
  region = "us-east-1" }

# Busca Ubuntu 22.04 LTS, versao mais recente
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# Cria o Grupo de Segurança (Firewall)
resource "aws_security_group" "agente_sg" {
  name        = "agente-email-sg"
  description = "Permite SSH e acesso ao painel do Streamlit"

  # Porta 22 para acesso ao Terminal via SSH,. em produção não usar ssh
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] 
  }

  # Porta 8501 para a interface web do Streamlit
  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Permite que a máquina acesse a internet (baixar pacotes, e-mails, etc) Em produção estudr melhor como é a rede, se for private ou usar loadbalancer
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Cria a Instância EC2
resource "aws_instance" "agente_ia" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "g4dn.xlarge"

  # Vincula o Firewall criado acima
  vpc_security_group_ids = [aws_security_group.agente_sg.id]

  # IMPORTANTE: Coloque aqui o nome da Key Pair via SSH
  key_name = "minha-chave-aws" 

  # Configuração do Disco
  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  # maquina spot para teste, para produção não pode ser spot.
  instance_market_options {
    market_type = "spot"
  }

  # Script de Inicialização (Roda automaticamente ao ligar a máquina)
  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get upgrade -y
              
              # Instala o Ollama automaticamente
              curl -fsSL https://ollama.com/install.sh | sh
              EOF

  tags = {
    Name = "Agente-Email-IA"
  }
}

# Exibe o IP Público no terminal quando o Terraform terminar
output "ip_publico" {
  value       = aws_instance.agente_ia.public_ip
  description = "O IP público da máquina para você acessar via SSH e Streamlit"
}