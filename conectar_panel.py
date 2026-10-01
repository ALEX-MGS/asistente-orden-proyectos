"""Conecta un panel recién exportado a la base.

    python conectar_panel.py ~/Downloads/panel-nuevo.html

Tú sigues diseñando el panel donde quieras — en otro chat, a mano, como
sea. Cuando lo exportes, este comando le cambia la capa de datos y lo
deja en estatico/panel.html listo para desplegar.

Toca lo siguiente y nada más:
  · quita los datos de fábrica (vienen del servidor)
  · load() lee de /api/estado
  · las etapas y Terminado escriben en la base
  · edición: nota, fecha, renombrar mueble y grupo, editar proyecto,
    palomear pendientes de obra y oficina, estado y nota de cotización
  · Deshacer llama al servidor; Rehacer se va (allá no existe)
  · el encabezado muestra si está en vivo

Lo que sigue pasando por save() —y por lo tanto sólo avisa— es crear,
eliminar y reordenar.

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

// Guarda un cambio suelto. Pinta primero y confirma después: el tablero
// se ve al momento y la base se pone al día en segundo plano. Si el
// servidor dice que no, 'revertir' regresa la pantalla como estaba y te
// dice por qué — nunca te deja creyendo que se guardó.
function guardar(accion, cuerpo, revertir){
  renderAll();
  apiPost('accion', Object.assign({accion:accion}, cuerpo))
    .then(o=>{ if(o&&o.v)versionActual=o.v; marcarSincronizado(); })
    .catch(e=>{
      if(revertir)revertir();
      renderAll();
      aviso('No se guardó: '+e.message,false);
    });
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
    versionActual=o.v||null;
    marcarSincronizado();
  }catch(e){
    aviso('No se pudo cargar el tablero: '+e.message,false);
  }finally{
    cargando=false;
  }
  pushHist();
  renderAll();
}

// Crear, eliminar y reordenar todavía pasan por aquí: avisa y recarga,
// para no dejarte creyendo que se guardó.
function save(){
  pushHist();
  renderAll();
  aviso('Crear y eliminar todavía no se guardan desde el panel. Por ahora, pídeselo al asistente por WhatsApp.',false);
  setTimeout(load,400);
}

let versionActual=null;

// Cada 8 segundos pregunta una sola cosa: "¿cambió algo?". Son unos
// bytes. Sólo cuando la respuesta cambia se trae el tablero completo.
// Así, lo que actualices por WhatsApp aparece aquí casi de inmediato.
async function revisarCambios(){
  if(editorCfg||cargando)return;
  try{
    const r=await fetch(API('version'),{cache:'no-store'});
    if(!r.ok)return;
    const o=await r.json();
    if(versionActual===null){versionActual=o.v;return}
    if(o.v!==versionActual){versionActual=o.v;load()}
  }catch(e){}
}

setInterval(revisarCambios, 8000);
setInterval(()=>{ if(!editorCfg) load(); }, 300000);   // red de seguridad
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&!editorCfg) revisarCambios();
});

'''

MANEJADOR_ETAPA = '''  }else if(act==='stage'&&proy){
    const it=proy.items.find(x=>x.id===btn.dataset.iid);
    if(!it)return;
    const si=+btn.dataset.si, previo=it.stages[si];
    it.stages[si]=!previo; renderAll();          // se pinta ya, se confirma después
    apiPost('etapa',{mueble_id:it.id,etapa:CLAVES[si],hecho:it.stages[si]})
      .then(r=>{ it.terminado=!!r.terminado; if(r.v)versionActual=r.v;
                 renderAll(); marcarSincronizado(); })
      .catch(e=>{ it.stages[si]=previo; renderAll();
                  aviso('No se guardó: '+e.message,false); });'''

MANEJADOR_TERMINADO = '''  }else if(act==='terminado'&&proy){
    const it=proy.items.find(x=>x.id===btn.dataset.iid);
    if(!it)return;
    const previo=it.terminado, etapasPrevias=it.stages.slice();
    it.terminado=!previo;
    // Marcar Terminado cierra también las cinco etapas, como en la base.
    // Desmarcar no las toca: que no esté terminado no significa que nunca
    // se barnizó.
    if(it.terminado)it.stages=[true,true,true,true,true];
    renderAll();
    apiPost('terminado',{mueble_id:it.id,terminado:it.terminado})
      .then(r=>{ if(r&&r.v)versionActual=r.v; marcarSincronizado(); })
      .catch(e=>{ it.terminado=previo; it.stages=etapasPrevias; renderAll();
                  aviso('No se guardó: '+e.message,false); });'''


# ---------------------------------------------------------------------
# Edición (tanda 1). Cada par es el renglón original del panel y el que
# lo sustituye. Son reemplazos cortos y únicos a propósito: si el panel
# cambió de forma, falla justo el que ya no aplica y se ve cuál.
# ---------------------------------------------------------------------
EDICIONES: list[tuple[str, str, str]] = [
    (
        "editar proyecto",
        "      onOk:([v,f])=>{if(!v)return;proy.nombre=v;proy.fechaEntrega=f||'';save();renderAll();}});",
        """      onOk:([v,f])=>{
        if(!v)return;
        const antes={n:proy.nombre,f:proy.fechaEntrega};
        proy.nombre=v; proy.fechaEntrega=f||'';
        guardar('editar_obra',{obra_id:proy.id,cambios:{nombre:v,fecha_entrega:f||null}},
                ()=>{proy.nombre=antes.n;proy.fechaEntrega=antes.f});
      }});""",
    ),
    (
        "fecha del mueble",
        "      onOk:([v])=>{it.fecha=v||'';save();renderAll();}});",
        """      onOk:([v])=>{
        const antes=it.fecha;
        it.fecha=v||'';
        guardar('fecha',{mueble_id:it.id,fecha:v||null},()=>{it.fecha=antes});
      }});""",
    ),
    (
        "renombrar mueble",
        "      onOk:([v])=>{if(!v)return;it.nombre=v;save();renderAll();}});",
        """      onOk:([v])=>{
        if(!v||v===it.nombre)return;
        const antes=it.nombre;
        it.nombre=v;
        guardar('renombrar_mueble',{mueble_id:it.id,nombre:v},()=>{it.nombre=antes});
      }});""",
    ),
    (
        "renombrar grupo",
        """      onOk:([v])=>{
        if(!v)return;
        proy.items.forEach(it=>{if(it.grupo===g)it.grupo=v});
        save();renderAll();
      }});""",
        """      onOk:([v])=>{
        if(!v||v===g)return;
        const tocados=proy.items.filter(it=>it.grupo===g);
        tocados.forEach(it=>{it.grupo=v});
        guardar('renombrar_grupo',{obra_id:proy.id,grupo:g,nuevo:v},
                ()=>{tocados.forEach(it=>{it.grupo=g})});
      }});""",
    ),
    (
        "nota del mueble",
        "      onOk:([v])=>{it.nota=v;save();renderAll();}});",
        """      onOk:([v])=>{
        const antes=it.nota;
        it.nota=v;
        guardar('nota',{mueble_id:it.id,nota:v},()=>{it.nota=antes});
      }});""",
    ),
    (
        "palomear pendiente de obra",
        """    const t=o&&o.tasks.find(x=>x.id===btn.dataset.tid);
    if(t){t.done=!t.done;save();renderAll();}""",
        """    const t=o&&o.tasks.find(x=>x.id===btn.dataset.tid);
    if(!t)return;
    t.done=!t.done;
    guardar('pendiente',{pendiente_id:t.id,hecho:t.done},()=>{t.done=!t.done});""",
    ),
    (
        "palomear pendiente de oficina",
        """  }else if(act==='of-toggle'){
    const o=oficina.find(x=>x.id===btn.dataset.oid);
    if(o){o.done=!o.done;save();renderAll();}""",
        """  }else if(act==='of-toggle'){
    const o=oficina.find(x=>x.id===btn.dataset.oid);
    if(!o)return;
    o.done=!o.done;
    guardar('pendiente',{pendiente_id:o.id,hecho:o.done},()=>{o.done=!o.done});""",
    ),
    (
        "nota de la cotización",
        "      onOk:([v])=>{c.nota=v;save();renderAll();}});",
        """      onOk:([v])=>{
        const antes=c.nota;
        c.nota=v;
        guardar('editar_cotizacion',{cotizacion_id:c.id,cambios:{nota:v}},()=>{c.nota=antes});
      }});""",
    ),
    (
        "estado de la cotización",
        """  const c=cotizaciones.find(x=>x.id===sel.dataset.cid);
  if(c){c.estado=sel.value;save();renderAll();}
});""",
        """  const c=cotizaciones.find(x=>x.id===sel.dataset.cid);
  if(!c)return;
  const antes=c.estado;
  c.estado=sel.value;
  guardar('editar_cotizacion',{cotizacion_id:c.id,cambios:{estado:sel.value}},
          ()=>{c.estado=antes});
});""",
    ),
]

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


def reemplazar(s, viejo, nuevo, etiqueta, fallos, veces=1, unico=False):
    """Sustituye un texto exacto. Si no está, lo anota como fallo.

    Con unico=True exige que aparezca una sola vez: así un parche nunca
    se aplica al renglón equivocado por parecerse a otro.
    """
    n = s.count(viejo)
    if n == 0:
        fallos.append(etiqueta)
        return s
    if unico and n > 1:
        fallos.append(f"{etiqueta} (aparece {n} veces, no sé cuál es)")
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

    # 4b. los botones de edición escriben en la base
    for etiqueta, viejo, nuevo in EDICIONES:
        s = reemplazar(s, viejo, nuevo, etiqueta, fallos, unico=True)

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
