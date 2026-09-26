"""Conecta un panel recién exportado a la base.

    python conectar_panel.py ~/Downloads/panel-nuevo.html

Tú sigues diseñando el panel donde quieras — en otro chat, a mano, como
sea. Cuando lo exportes, este comando le cambia la capa de datos y lo
deja en estatico/panel.html listo para desplegar.

Toca seis cosas y nada más:
  · quita los datos de fábrica (vienen del servidor)
  · load() lee de /api/estado
  · las etapas y Terminado escriben en la base
  · Deshacer llama al servidor; Rehacer se va (allá no existe)
  · el encabezado muestra si está en vivo

Si el panel cambió de forma y algún parche ya no aplica, lo dice y no
escribe nada. Nunca deja un panel a medio conectar.
"""
import io
import re
import shutil
import sys
from pathlib import Path

DESTINO = Path(__file__).resolve().parent / "estatico" / "panel.html"

CAPA_DATOS = '''// ===== DATOS: vienen del servidor, no del navegador =====
const TOKEN=new URLSearchParams(location.search).get('k')||'';
const API=(r)=>'/api/'+r+(TOKEN?'?k='+encodeURIComponent(TOKEN):'');
const CLAVES=['aprobado','carpinteria','barniz','entrega','instalacion'];
let cargando=false;

function aviso(texto,ok){
  const el=$('io-msg');
  if(!el)return;
  el.classList.remove('hidden');
  el.className='result '+(ok?'r-ok':'r-err');
  el.textContent=texto;
  clearTimeout(aviso._t);
  aviso._t=setTimeout(()=>el.classList.add('hidden'),6000);
}

async function apiPost(ruta, cuerpo){
  const r=await fetch(API(ruta),{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(cuerpo||{})
  });
  const txt=await r.text();
  let o; try{o=JSON.parse(txt)}catch(e){o={error:txt.slice(0,140)}}
  if(!r.ok||o.error)throw new Error(o.error||('el servidor contestó '+r.status));
  return o;
}

function marcarSincronizado(){
  const el=$('sello-sync');
  if(!el)return;
  const h=new Date().toLocaleTimeString('es-MX',{hour:'2-digit',minute:'2-digit'});
  el.textContent='En vivo · '+h;
}

async function load(){
  if(cargando)return;
  cargando=true;
  try{
    const r=await fetch(API('estado'),{cache:'no-store'});
    if(r.status===403)throw new Error('El link no trae el código de acceso correcto.');
    if(!r.ok)throw new Error('El servidor contestó '+r.status);
    const o=await r.json();
    proyectos=o.proyectos||[];
    pends=o.pends||[];
    cotizaciones=o.cotizaciones||[];
    oficina=o.oficina||[];
    marcarSincronizado();
  }catch(e){
    aviso('No se pudo cargar el tablero: '+e.message,false);
  }finally{
    cargando=false;
  }
  pushHist();
  renderAll();
}

// Lo que todavía no escribe en la base pasa por aquí: avisa y recarga,
// para no dejarte creyendo que se guardó.
function save(){
  pushHist();
  renderAll();
  aviso('Eso todavía no se guarda desde el panel. Por ahora, pídeselo al asistente por WhatsApp.',false);
  setTimeout(load,400);
}

setInterval(()=>{ if(!editorCfg) load(); }, 60000);
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&!editorCfg) load();
});

'''

MANEJADOR_ETAPA = '''  }else if(act==='stage'&&proy){
    const it=proy.items.find(x=>x.id===btn.dataset.iid);
    if(!it)return;
    const si=+btn.dataset.si, previo=it.stages[si];
    it.stages[si]=!previo; renderAll();          // se pinta ya, se confirma después
    apiPost('etapa',{mueble_id:it.id,etapa:CLAVES[si],hecho:it.stages[si]})
      .then(r=>{ it.terminado=!!r.terminado; renderAll(); marcarSincronizado(); })
      .catch(e=>{ it.stages[si]=previo; renderAll();
                  aviso('No se guardó: '+e.message,false); });'''

MANEJADOR_TERMINADO = '''  }else if(act==='terminado'&&proy){
    const it=proy.items.find(x=>x.id===btn.dataset.iid);
    if(!it)return;
    const previo=it.terminado;
    it.terminado=!previo; renderAll();
    apiPost('terminado',{mueble_id:it.id,terminado:it.terminado})
      .then(()=>{ marcarSincronizado(); })
      .catch(e=>{ it.terminado=previo; renderAll();
                  aviso('No se guardó: '+e.message,false); });'''

MANEJADOR_UNDO = '''  if(act==='undo'){
    apiPost('deshacer',{})
      .then(r=>{
        if(!r.ok){aviso(r.motivo||'No hay nada que deshacer',false);return}
        aviso('Deshecho: '+r.revertidos+(r.revertidos===1?' cambio':' cambios'),true);
        load();
      })
      .catch(e=>aviso('No se pudo deshacer: '+e.message,false));
    return;
  }
  if(act==='redo'){return}   // el servidor no rehace: el botón se oculta'''


def cortar(s, ini, fin, nuevo, etiqueta, fallos):
    """Reemplaza el bloque entre dos marcas. Avisa si no lo encuentra."""
    try:
        a = s.index(ini)
        b = s.index(fin, a)
    except ValueError:
        fallos.append(etiqueta)
        return s
    return s[:a] + nuevo + s[b:]


def reemplazar(s, viejo, nuevo, etiqueta, fallos, veces=1):
    if viejo not in s:
        fallos.append(etiqueta)
        return s
    return s.replace(viejo, nuevo, veces)


def conectar(html: str) -> tuple[str, list[str]]:
    fallos: list[str] = []
    s = html

    # 1. fuera los datos de fábrica
    s = cortar(s, 'let proyectos=[', 'let cotizaciones=[];',
               "let proyectos=[];\nlet pends=[];\n",
               "datos de fábrica", fallos)

    # 2. la capa de datos completa
    s = cortar(s, 'async function load(){', '// ===== RESPALDO',
               CAPA_DATOS, "load() y save()", fallos)

    # 3. restaurar() ya no escribe en el navegador
    s = s.replace("  if(window.storage)window.storage.set('gm-v2-data',snap).catch(()=>{});\n", "")

    # 4. etapas y Terminado escriben en la base
    s = cortar(s, "  }else if(act==='stage'&&proy){", "  }else if(act==='nota'",
               MANEJADOR_ETAPA + "\n", "manejador de etapas", fallos)
    s = cortar(s, "  }else if(act==='terminado'&&proy){", "  }else if(act==='ren-item'",
               MANEJADOR_TERMINADO + "\n", "manejador de Terminado", fallos)

    # 5. Deshacer al servidor, Rehacer fuera
    s = reemplazar(s,
                   "  if(act==='undo'){undo();return}\n  if(act==='redo'){redo();return}",
                   MANEJADOR_UNDO, "manejador de Deshacer", fallos)
    s = re.sub(r"\n\s*else if\(k==='y'\|\|\(k==='z'&&e\.shiftKey\)\)\{[^}]*\}", "", s)

    # 6. los botones: Deshacer siempre activo, Rehacer oculto
    s = re.sub(r"\['btn-undo','btn-undo-d'\]\.forEach\([^\n]*\);",
               "['btn-undo','btn-undo-d'].forEach(id=>{const b=$(id);if(b)b.disabled=false});",
               s)
    s = re.sub(r"\['btn-redo','btn-redo-d'\]\.forEach\([^\n]*\);",
               "['btn-redo','btn-redo-d'].forEach(id=>{const b=$(id);if(b)b.style.display='none'});",
               s)

    # 7. el sello de "en vivo" en el encabezado
    if 'id="sello-sync"' not in s:
        s = reemplazar(s, '<div class="sub">',
                       '<div class="sub"><span id="sello-sync" '
                       'style="float:right;font-size:11px;color:#1D9E75">conectando…</span>',
                       "sello de sincronía", fallos)

    if 'window.storage' in s:
        fallos.append("quedaron referencias a window.storage")
    return s, fallos


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    origen = Path(sys.argv[1]).expanduser()
    if not origen.is_file():
        print(f"No encuentro {origen}")
        return 1

    html = io.open(origen, encoding="utf-8").read()
    nuevo, fallos = conectar(html)

    if fallos:
        print("No se pudo conectar. Estos parches no encontraron dónde aplicarse:")
        for f in fallos:
            print("  ·", f)
        print("\nEl panel cambió de forma. No escribí nada.")
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    if DESTINO.exists():
        respaldo = DESTINO.with_suffix(".html.anterior")
        shutil.copy2(DESTINO, respaldo)
        print(f"Respaldo del anterior: {respaldo.name}")
    io.open(DESTINO, "w", encoding="utf-8").write(nuevo)

    print(f"Conectado: {origen.name} → estatico/panel.html "
          f"({len(html):,} → {len(nuevo):,} bytes)")
    print("\nFalta: git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
