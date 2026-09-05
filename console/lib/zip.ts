// Um zip "store" (sem compressão), escrito à mão para o console entregar as abas
// da planilha num arquivo só sem dependência nova. Os CSVs são pequenos (a maior aba
// tem milhares de linhas); comprimir não vale uma dependência, e o formato store é a
// parte trivial e estável do ZIP (PKWARE APPNOTE §4.3): cabeçalho local + dados por
// arquivo, diretório central, registro de fim. CRC-32 é obrigatório mesmo sem
// compressão, então vem junto.

const TABELA_CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

/** CRC-32 (IEEE 802.3), o do ZIP. */
export function crc32(dados: Uint8Array): number {
  let c = 0xffffffff;
  for (let i = 0; i < dados.length; i++) c = TABELA_CRC[(c ^ dados[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export type Entrada = { nome: string; dados: Uint8Array };

/** Teto do zip inteiro, bem abaixo dos 4 GiB do formato clássico (campos de 32 bits) e
 *  muito acima do tamanho real das abas (dezenas de KB). Passar dele é sinal de que
 *  algo está errado, e a resposta certa é falhar ANTES de escrever um byte — nunca
 *  emitir um contêiner com campo estourado, que abre numa ferramenta e corrompe em
 *  outra. */
export const TETO_BYTES = 256 * 1024 * 1024;

export class ZipGrandeDemais extends Error {}

function dataDos(d: Date): { data: number; hora: number } {
  // Formato MS-DOS: ano desde 1980 (7 bits), mês, dia; hora, minuto, segundo/2.
  const ano = Math.max(1980, d.getFullYear());
  return {
    data: ((ano - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
    hora: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
  };
}

/** Monta o zip em memória. Nomes em UTF-8 (flag bit 11). `quando` é o carimbo de
 *  data das entradas e é PARÂMETRO, não relógio: o mesmo conteúdo com a mesma data
 *  produz os mesmos bytes (o chamador passa a data de referência da rodada). */
export function zipStore(entradas: readonly Entrada[], quando: Date): Uint8Array {
  const enc = new TextEncoder();
  const { data, hora } = dataDos(quando);
  // A conta usa os BYTES do nome (UTF-8), os mesmos que vão para os cabeçalhos — não
  // o comprimento da string, que conta unidades UTF-16 e subestima nome acentuado.
  const nomes = entradas.map((e) => enc.encode(e.nome));
  for (const n of nomes) if (n.length > 0xffff) throw new ZipGrandeDemais(`nome de ${n.length} bytes não cabe em 16 bits`);
  const total = entradas.reduce((s, e, i) => s + 30 + 46 + 2 * nomes[i].length + e.dados.length, 22);
  if (total > TETO_BYTES)
    throw new ZipGrandeDemais(`o zip teria ${total} bytes, acima do teto de ${TETO_BYTES}`);
  const partes: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let deslocamento = 0;

  for (const [i, e] of entradas.entries()) {
    const nome = nomes[i];
    const crc = crc32(e.dados);
    const tam = e.dados.length;

    const local = new DataView(new ArrayBuffer(30));
    local.setUint32(0, 0x04034b50, true);
    local.setUint16(4, 20, true); // versão necessária: 2.0
    local.setUint16(6, 0x0800, true); // bit 11: nomes em UTF-8
    local.setUint16(8, 0, true); // método 0 = store
    local.setUint16(10, hora, true);
    local.setUint16(12, data, true);
    local.setUint32(14, crc, true);
    local.setUint32(18, tam, true);
    local.setUint32(22, tam, true);
    local.setUint16(26, nome.length, true);
    local.setUint16(28, 0, true);
    partes.push(new Uint8Array(local.buffer), nome, e.dados);

    const cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true);
    cd.setUint16(4, 20, true); // feita por
    cd.setUint16(6, 20, true); // necessária
    cd.setUint16(8, 0x0800, true);
    cd.setUint16(10, 0, true);
    cd.setUint16(12, hora, true);
    cd.setUint16(14, data, true);
    cd.setUint32(16, crc, true);
    cd.setUint32(20, tam, true);
    cd.setUint32(24, tam, true);
    cd.setUint16(28, nome.length, true);
    cd.setUint16(30, 0, true); // extra
    cd.setUint16(32, 0, true); // comentário
    cd.setUint16(34, 0, true); // disco
    cd.setUint16(36, 0, true); // atributos internos
    cd.setUint32(38, 0, true); // atributos externos
    cd.setUint32(42, deslocamento, true);
    central.push(new Uint8Array(cd.buffer), nome);

    deslocamento += 30 + nome.length + tam;
  }

  const tamCentral = central.reduce((s, p) => s + p.length, 0);
  const fim = new DataView(new ArrayBuffer(22));
  fim.setUint32(0, 0x06054b50, true);
  fim.setUint16(4, 0, true);
  fim.setUint16(6, 0, true);
  fim.setUint16(8, entradas.length, true);
  fim.setUint16(10, entradas.length, true);
  fim.setUint32(12, tamCentral, true);
  fim.setUint32(16, deslocamento, true);
  fim.setUint16(20, 0, true);

  const todas = [...partes, ...central, new Uint8Array(fim.buffer)];
  const saida = new Uint8Array(todas.reduce((s, p) => s + p.length, 0));
  let pos = 0;
  for (const p of todas) {
    saida.set(p, pos);
    pos += p.length;
  }
  return saida;
}
