async function json(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

const money = (n) => Number(n || 0).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});

const parseBR = (s) => {
  if (typeof s === 'number') return s;
  s = (s ?? '').toString().replace(/[R$\s]/g,'').trim();
  if (s.includes(',')) {
    s = s.replace(/\./g,'').replace(',', '.');
  }
  const v = parseFloat(s);
  return isNaN(v) ? 0 : v;
};

let DATA = [];

// -------------------- PRODUTOS / FRETE --------------------
async function loadUF(){
  const sel = document.getElementById('uf');
  const hint = document.getElementById('freteHint');
  if(!sel || !hint) return;

  sel.innerHTML = '<option>Selecione...</option>';
  hint.textContent = 'Buscando frete...';
  try{
    const js = await json('/api/fretes');
    js.data.forEach(f => {
      const o = document.createElement('option');
      o.value = f.uf;
      o.textContent = f.uf;
      o.dataset.valor = f.valor;
      sel.appendChild(o);
    });
    hint.textContent = 'Frete carregado.';
    sel.onchange = () => {
      const opt = sel.options[sel.selectedIndex];
      document.getElementById('frete').value = (Number(opt?.dataset?.valor || 0))
        .toLocaleString('pt-BR',{minimumFractionDigits:2});
    };
  }catch(e){
    hint.textContent = 'Erro ao ler frete';
  }
}

async function loadProdutos(){
  const tbody = document.getElementById('tbody');
  if(!tbody) return;

  tbody.innerHTML = '<tr><td colspan="5">Carregando...</td></tr>';
  try{
    const js = await json('/api/produtos');
    if(!js.ok) throw new Error(js.error || 'Falha');
    DATA = js.data;
    tbody.innerHTML = '';
    js.data.forEach((p,i) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td><input type="checkbox" class="pick" data-i="${i}"></td>
                      <td>${p.produto}</td>
                      <td>${money(p.cartao)}</td>
                      <td>${money(p.avista)}</td>
                      <td>${money(p.dezx)}</td>`;
      tbody.appendChild(tr);
    });
    if(!js.data.length){
      tbody.innerHTML = '<tr><td colspan="5">Nenhum item encontrado.</td></tr>';
    }
  }catch(e){
    tbody.innerHTML = '<tr><td colspan="5">Erro ao carregar produtos</td></tr>';
  }
}

// -------------------- MENSAGENS --------------------
function buildMsg(p, frete, descInput, uf){
  const desc = Math.min(100, Math.max(0, Number(descInput) || 0));

  const total = p.cartao + frete;
  const parcela = total / 10;

  const cartaoComDesconto = p.cartao - (p.cartao * (desc / 100));
  const promo = cartaoComDesconto + frete;

  const descTxt = `${Math.round(desc)}%`;

  return `*VALOR JÁ INCLUSO O FRETE PARA ${uf || 'UF'}*
*${p.produto}*
${(p.indicada || '').trim()}

${money(total)}
até 10x de ${money(parcela)} sem juros
ou
*PROMOÇÃO: ${money(promo)} no pix já com ${descTxt} de desconto*`;
}

function getSelectedContext(){
  const freteInput = document.getElementById('frete');
  const descInput = document.getElementById('desc');
  const ufSel = document.getElementById('uf');

  const frete = freteInput ? parseBR(freteInput.value) : 0;
  let desc = descInput ? parseBR(descInput.value) : 0;
  desc = Math.min(100, Math.max(0, Number(desc) || 0));

  const uf = ufSel ? ufSel.value : '';
  const picks = [...document.querySelectorAll('.pick:checked')].map(x => Number(x.dataset.i));
  const items = picks.map(i => DATA[i]).filter(Boolean);

  return {items, frete, desc, uf};
}

function calc(){
  const wrap = document.getElementById('result');
  if(!wrap) return;

  const {items, frete, desc, uf} = getSelectedContext();
  wrap.innerHTML = '';

  if(!items.length){
    wrap.innerHTML = '<div class="small">Selecione pelo menos 1 produto.</div>';
    return;
  }

  items.forEach(p => {
    const box = document.createElement('div');
    box.className = 'msg';
    const img = p.imagem
      ? `<img src="${p.imagem}" alt="${p.produto}">`
      : `<div class="small">Sem imagem</div>`;
    const msg = buildMsg(p, frete, desc, uf);
    box.innerHTML = `${img}
      <div>
        <textarea>${msg}</textarea>
        <div class="actions"><button class="ghost copy">Copiar</button></div>
      </div>`;
    box.querySelector('.copy').addEventListener('click', () => {
      const ta = box.querySelector('textarea');
      ta.select();
      document.execCommand('copy');
    });
    wrap.appendChild(box);
  });
}

// -------------------- NORMALIZAÇÃO DO NÚMERO --------------------
function normalizeNumeroInput(){
  const inp = document.getElementById('numero');
  if(!inp) return;
  let v = inp.value;
  if(!v){
    return;
  }
  const hasPlus = v.trim().startsWith('+');
  const digits = v.replace(/\D/g,'');
  if(!digits){
    inp.value = hasPlus ? '+' : '';
    return;
  }
  if(hasPlus){
    inp.value = '+' + digits;
  }else{
    inp.value = digits;
  }
}

// -------------------- ENVIO CHATGURU --------------------
async function sendChatguru(){
  const statusEl = document.getElementById('sendStatus');
  const numeroInput = document.getElementById('numero');
  if(!statusEl || !numeroInput) return;

  const numero = (numeroInput.value || '').trim();
  statusEl.textContent = '';

  if(!numero){
    statusEl.textContent = 'Informe o número do WhatsApp.';
    return;
  }

  const {items, frete, desc, uf} = getSelectedContext();

  if(!items.length){
    statusEl.textContent = 'Selecione pelo menos 1 produto para enviar.';
    return;
  }

  const mensagens = items.map(p => ({
    texto: buildMsg(p, frete, desc, uf),
    imagem_url: p.imagem
  }));

  const payload = {
    numero,
    mensagens
  };

  try{
    statusEl.textContent = 'Enviando pelo ChatGuru...';

    const resp = await fetch('/api/enviar_chatguru', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });

    const js = await resp.json().catch(() => ({}));

    if(resp.ok && js.ok){
      statusEl.textContent = 'Mensagens enviadas com sucesso!';
    }else{
      statusEl.textContent = 'Falha ao enviar: ' + (js.error || 'veja detalhes no console');
      console.log('Detalhes envio ChatGuru', js);
    }
  }catch(e){
    statusEl.textContent = 'Erro de comunicação com o servidor.';
  }
}

// -------------------- CONFIG CHATGURU (PÁGINA /config) --------------------
async function loadChatguruConfig(){
  const form = document.getElementById('chatguru_form');
  if(!form) return;

  const statusEl = document.getElementById('cfg_status');
  const debugEl = document.getElementById('cfg_debug');
  statusEl.textContent = 'Carregando...';
  debugEl.textContent = '';

  try{
    const js = await json('/api/chatguru_config');
    if(js.ok && js.data){
      document.getElementById('cfg_endpoint').value = js.data.api_endpoint || '';
      document.getElementById('cfg_key').value = js.data.chatguru_key || '';
      document.getElementById('cfg_account').value = js.data.chatguru_account_id || '';
      document.getElementById('cfg_phone').value = js.data.chatguru_phone_id || '';
      document.getElementById('cfg_dialog').value = js.data.chatguru_dialog_id || '';
      document.getElementById('cfg_msg1').value = js.data.msg_final_um || '';
      document.getElementById('cfg_msg_varios').value = js.data.msg_final_varios || '';
      document.getElementById('cfg_desc_padrao').value = js.data.desconto_padrao ?? '';
      statusEl.textContent = 'Configuração carregada.';
    }else{
      statusEl.textContent = 'Falha ao carregar configuração.';
    }
  }catch(e){
    statusEl.textContent = 'Erro ao carregar configuração.';
  }
}

async function saveChatguruConfig(){
  const form = document.getElementById('chatguru_form');
  if(!form) return;

  const statusEl = document.getElementById('cfg_status');
  const debugEl = document.getElementById('cfg_debug');
  statusEl.textContent = 'Salvando...';
  debugEl.textContent = '';

  const payload = {
    api_endpoint: document.getElementById('cfg_endpoint').value || '',
    chatguru_key: document.getElementById('cfg_key').value || '',
    chatguru_account_id: document.getElementById('cfg_account').value || '',
    chatguru_phone_id: document.getElementById('cfg_phone').value || '',
    chatguru_dialog_id: document.getElementById('cfg_dialog').value || '',
    msg_final_um: document.getElementById('cfg_msg1').value || '',
    msg_final_varios: document.getElementById('cfg_msg_varios').value || '',
    desconto_padrao: parseFloat(document.getElementById('cfg_desc_padrao').value || '0') || 0,
  };

  try{
    const resp = await fetch('/api/chatguru_config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const js = await resp.json().catch(() => ({}));
    if(resp.ok && js.ok){
      statusEl.textContent = 'Parâmetros salvos com sucesso.';
    }else{
      statusEl.textContent = 'Erro ao salvar parâmetros.';
      debugEl.textContent = JSON.stringify(js, null, 2);
    }
  }catch(e){
    statusEl.textContent = 'Erro ao salvar parâmetros.';
  }
}

async function testChatguruConnection(){
  const form = document.getElementById('chatguru_form');
  if(!form) return;

  const statusEl = document.getElementById('cfg_status');
  const debugEl = document.getElementById('cfg_debug');
  const numero = (document.getElementById('cfg_teste_numero').value || '').trim();

  if(!numero){
    statusEl.textContent = 'Informe um número para teste.';
    return;
  }

  statusEl.textContent = 'Testando conexão...';
  debugEl.textContent = '';

  try{
    const resp = await fetch('/api/chatguru_test', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({numero_teste: numero})
    });
    const js = await resp.json().catch(() => ({}));

    debugEl.textContent = JSON.stringify(js.resposta || js, null, 2);

    if(resp.ok && js.ok){
      statusEl.textContent = 'Conexão OK (status ' + js.status + ').';
    }else{
      const desc = js.description || js.error || 'Erro desconhecido';
      statusEl.textContent = 'Falha na conexão: ' + desc + (js.hint ? ' | ' + js.hint : '');
    }
  }catch(e){
    statusEl.textContent = 'Erro ao testar conexão.';
  }
}

// -------------------- USO DO DESCONTO PADRÃO NA TELA PRINCIPAL --------------------
async function applyDefaultDiscount(){
  const descInput = document.getElementById('desc');
  if(!descInput) return;
  try{
    const js = await json('/api/chatguru_config');
    if(js.ok && js.data && js.data.desconto_padrao !== undefined){
      descInput.value = js.data.desconto_padrao;
    }
  }catch(e){
    // silencioso
  }
}

// -------------------- INIT --------------------
window.addEventListener('load', () => {
  // Página principal
  if(document.getElementById('tbody')){
    loadUF();
    loadProdutos();
    applyDefaultDiscount();
    const reloadBtn = document.getElementById('reload');
    if(reloadBtn) reloadBtn.onclick = () => {
      loadUF();
      loadProdutos();
    };
    const calcBtn = document.getElementById('calc');
    if(calcBtn) calcBtn.onclick = calc;
    const btnSend = document.getElementById('send');
    if(btnSend) btnSend.onclick = sendChatguru;
    const numeroInput = document.getElementById('numero');
    if(numeroInput) numeroInput.addEventListener('input', normalizeNumeroInput);
  }

  // Página de configurações
  if(document.getElementById('chatguru_form')){
    loadChatguruConfig();
    const saveBtn = document.getElementById('cfg_save');
    const testBtn = document.getElementById('cfg_test');
    if(saveBtn) saveBtn.onclick = saveChatguruConfig;
    if(testBtn) testBtn.onclick = testChatguruConnection;
  }
});
