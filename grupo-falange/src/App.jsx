import { useEffect, useRef } from 'react';
import { motion, useAnimation, useInView } from 'framer-motion';

// Componente para animação ao scroll
const AnimatedSection = ({ children, delay = 0 }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.2 });
  const controls = useAnimation();

  useEffect(() => {
    if (isInView) {
      controls.start('visible');
    }
  }, [isInView, controls]);

  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={controls}
      variants={{
        hidden: { opacity: 0, y: 50 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.6, delay } }
      }}
    >
      {children}
    </motion.div>
  );
};

// Botão com animação de clique (scale + hover)
const LuxuriousButton = ({ children, onClick, outline = false }) => {
  return (
    <motion.button
      whileHover={{ scale: 1.05, boxShadow: '0 0 15px rgba(255,255,255,0.2)' }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className={`px-8 py-3 rounded-full font-semibold text-sm uppercase tracking-wider transition-all duration-300 ${
        outline
          ? 'bg-transparent border border-white/40 text-white hover:border-white hover:bg-white/5'
          : 'bg-white text-black hover:bg-white/90'
      }`}
    >
      {children}
    </motion.button>
  );
};

// Card de valor
const ValueCard = ({ title, description, delay }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      whileInView={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay }}
      viewport={{ once: true }}
      className="bg-[#111111] p-6 rounded-2xl border border-white/5 hover:border-white/20 transition-all duration-300 hover:shadow-xl hover:shadow-white/5"
    >
      <h3 className="text-xl font-light tracking-wide mb-3 text-white/90">{title}</h3>
      <p className="text-gray-400 text-sm leading-relaxed">{description}</p>
    </motion.div>
  );
};

function App() {
  const scrollToContact = () => {
    document.getElementById('contato')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="bg-black text-white font-sans antialiased">
      {/* Header fixo com efeito glass */}
      <header className="fixed top-0 w-full z-50 backdrop-blur-md bg-black/30 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="text-2xl font-light tracking-tighter">
            Grupo <span className="font-bold tracking-normal">Falange</span>
          </div>
          <nav className="hidden md:flex space-x-8 text-sm font-light">
            <a href="#valores" className="hover:text-white/70 transition">Valores</a>
            <a href="#solucao" className="hover:text-white/70 transition">Solução</a>
            <a href="#contato" className="hover:text-white/70 transition">Contato</a>
          </nav>
          <LuxuriousButton outline onClick={scrollToContact}>Fale com um especialista</LuxuriousButton>
        </div>
      </header>

      <main className="pt-24">
        {/* Hero Section */}
        <section className="relative min-h-[90vh] flex items-center justify-center px-6 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-black via-gray-900 to-black opacity-90"></div>
          <div className="relative z-10 text-center max-w-4xl mx-auto">
            <motion.h1
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8 }}
              className="text-5xl md:text-7xl font-bold tracking-tighter bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent"
            >
              Atendimento que vende
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.8 }}
              className="text-gray-300 text-lg md:text-2xl mt-6 max-w-2xl mx-auto"
            >
              CRM automatizado para pizzarias e pequenos restaurantes. <br />
              Inteligente, fluido e humano.
            </motion.p>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="mt-10"
            >
              <LuxuriousButton onClick={scrollToContact}>Solicitar demonstração</LuxuriousButton>
            </motion.div>
          </div>
          <div className="absolute bottom-10 left-1/2 transform -translate-x-1/2 animate-bounce">
            <div className="w-6 h-10 border-2 border-white/30 rounded-full flex justify-center">
              <div className="w-1 h-2 bg-white/60 rounded-full mt-2 animate-pulse"></div>
            </div>
          </div>
        </section>

        {/* Seção Valores */}
        <section id="valores" className="py-24 px-6 max-w-7xl mx-auto">
          <AnimatedSection>
            <h2 className="text-3xl md:text-4xl font-light text-center tracking-tight">
              Por que os melhores escolhem a <span className="font-bold">Falange</span>
            </h2>
            <p className="text-center text-gray-400 mt-4 max-w-2xl mx-auto">
              Seis valores que transformam o atendimento do seu negócio.
            </p>
          </AnimatedSection>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mt-16">
            <ValueCard title="Inteligente" description="IA que aprende os hábitos dos seus clientes e sugere upsell automaticamente." delay={0} />
            <ValueCard title="Fluido" description="Integração com WhatsApp, iFood e telefonia. Tudo em um só lugar." delay={0.1} />
            <ValueCard title="Humano" description="Atendimento natural, com tom de voz personalizado e empatia programada." delay={0.2} />
            <ValueCard title="Minimalista" description="Interface limpa, sem ruídos. Foco no que importa: vender mais." delay={0.3} />
            <ValueCard title="Escalável" description="Do food truck à rede de 20 lojas. Cresce com você." delay={0.4} />
            <ValueCard title="Intuitivo" description="Zero treinamento. Qualquer funcionário opera em 10 minutos." delay={0.5} />
          </div>
        </section>

        {/* Seção Solução */}
        <section id="solucao" className="py-24 px-6 bg-[#0a0a0a] border-y border-white/5">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center gap-12">
            <AnimatedSection delay={0.2}>
              <div className="flex-1">
                <div className="inline-block px-3 py-1 rounded-full bg-white/5 text-xs tracking-wider mb-4">ATENDIMENTO 24/7</div>
                <h2 className="text-3xl md:text-4xl font-light leading-tight">
                  Seu restaurante nunca mais <br />
                  <span className="font-bold">perde uma venda</span> fora do horário.
                </h2>
                <p className="text-gray-400 mt-6 leading-relaxed">
                  O CRM da Falange automatiza desde o primeiro "bom dia" até o pedido final. 
                  Reconhecimento de voz, cardápio dinâmico, pagamento integrado e pós-venda 
                  automático. Tudo com uma interface minimalista e relatórios em tempo real.
                </p>
                <ul className="mt-8 space-y-3">
                  {['📞 Atendimento por voz e texto', 'Automação de delivery e retirada', 'Dashboard inteligente com previsão de demanda'].map((item, i) => (
                    <motion.li key={i} initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.1 }} className="flex items-center gap-3 text-gray-300">
                      <span className="text-white text-xl">—</span> {item}
                    </motion.li>
                  ))}
                </ul>
              </div>
            </AnimatedSection>
            <div className="flex-1 flex justify-center">
              <motion.div
                initial={{ opacity: 0, rotateY: 30 }}
                whileInView={{ opacity: 1, rotateY: 0 }}
                transition={{ duration: 0.8 }}
                className="w-full max-w-md h-80 bg-gradient-to-br from-gray-800 to-black rounded-2xl border border-white/10 shadow-2xl flex items-center justify-center"
              >
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto rounded-full bg-white/5 flex items-center justify-center mb-4">
                    <svg className="w-8 h-8 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <p className="text-gray-500 text-sm">Interface do CRM — Preview</p>
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* Depoimento */}
        <section className="py-20 px-6 max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
            className="bg-[#111111] p-8 md:p-12 rounded-3xl border border-white/5"
          >
            <svg className="w-10 h-10 text-white/20 mx-auto mb-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M14.017 21v-7.391c0-5.704 3.731-9.57 8.983-10.609l.995 2.151c-2.432.917-3.995 3.638-3.995 5.849h4v10h-9.983zm-14.017 0v-7.391c0-5.704 3.748-9.57 9-10.609l.996 2.151c-2.433.917-3.996 3.638-3.996 5.849h3.983v10h-9.983z" />
            </svg>
            <p className="text-gray-300 text-lg md:text-xl leading-relaxed italic">
              “Aumentamos as vendas noturnas em 34% só com o atendimento automatizado. 
              Os clientes nem percebem que não é humano — e os que percebem, amam a agilidade.”
            </p>
            <p className="mt-6 text-white font-medium">— Carla Mendes, Pizzaria Verace</p>
          </motion.div>
        </section>

        {/* Call to Action */}
        <section id="contato" className="py-24 px-6 text-center bg-gradient-to-t from-black via-[#050505] to-black">
          <AnimatedSection>
            <h2 className="text-3xl md:text-5xl font-light tracking-tight">
              Pronto para um atendimento <span className="font-bold">realmente inteligente</span>?
            </h2>
            <p className="text-gray-400 max-w-xl mx-auto mt-4">
              Fale com nosso time e veja como a Falange se adapta ao seu negócio.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
              <LuxuriousButton onClick={() => alert('Simulação de envio para o CRM da Falange')}>
                Agendar demonstração
              </LuxuriousButton>
              <LuxuriousButton outline onClick={() => window.location.href = 'mailto:contato@grupofalange.com'}>
                contato@grupofalange.com
              </LuxuriousButton>
            </div>
          </AnimatedSection>
        </section>
      </main>

      <footer className="py-8 border-t border-white/5 text-center text-gray-500 text-sm">
        <div className="max-w-7xl mx-auto px-6">
          <p>© 2026 Grupo Falange — CRM de atendimento automatizado para restaurantes.</p>
          <p className="mt-2 text-xs">Feito para crescer com você.</p>
        </div>
      </footer>
    </div>
  );
}

export default App;