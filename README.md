# 💧 licitom AGUA

**Seguimiento de licitaciones públicas de operación y mantenimiento (O&M) del ciclo integral del agua en España.**

Quien prepara ofertas de O&M de agua pierde mucho tiempo en tareas de poco valor:

- Revisar a diario la Plataforma de Contratación entre cientos de anuncios ajenos al agua.
- Vigilar aclaraciones, cambios de plazo y pliegos rectificados.
- Hacer la primera lectura del PCAP y el PPTP.

**licitom AGUA** automatiza esa parte para llegar antes a lo importante: decidir si presentarse y cómo.

# Cómo usarlo

Entrar en licitom_AGUA.html, con un enlace directo a esa página de tu repositorio.
Pulsar el botón ⬇ Download raw file, a la derecha, junto a Raw.
Abrir el archivo descargado con doble clic en Edge o Chrome.

## Qué hace

| Función | Descripción |
|---|---|
| 🔎 **Detección** | Lee los datos abiertos oficiales de la Plataforma de Contratación del Sector Público y filtra solo las licitaciones de O&M del ciclo integral del agua. No duplica las que ya has visto. |
| ⭐ **Seguimiento** | Registra las novedades de las licitaciones que sigues: cambios de plazo o estado, nuevos documentos, adjudicaciones… |
| 📋 **Preguntas y respuestas** | Mantiene un Excel actualizado por expediente. |
| 📄 **Análisis de pliegos** | Riesgos (subrogación, revisión de precios, penalidades…), criterios de adjudicación y fórmula económica, citando cláusula y página. Cada dato indica si es *extracción* literal, *inferencia* o *estimación*. |
| 📉 **Estudio de baja** | Umbral de referencia del art. 85 RGLCAP, probabilidad de oferta anormal, puntos esperados y rango de baja razonable, con simulador Excel editable. |
| ✉️ **Resumen por correo** | Prepara un borrador con todas las novedades, listo para abrir en Outlook. |
| ⚠️ **Avisos de lectura** | Señala los pliegos escaneados o ilegibles que no puede analizar. |

## Cómo se usa

1. **Abre la app** (enlace de arriba o archivo descargado).
2. **Descarga el ZIP del mes** desde los datos abiertos de Hacienda:
   - [Licitaciones en perfiles del contratante](https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/Paginas/LicitacionesContratante.aspx)
   - [Licitaciones de plataformas agregadas](https://www.hacienda.gob.es/es-ES/GobiernoAbierto/Datos%20Abiertos/Paginas/LicitacionesAgregacion.aspx) *(opcional, más cobertura)*
3. **Arrastra el ZIP** a la app, sin descomprimirlo.
4. Pulsa **☆ Seguir** en las licitaciones que te interesen y, en su ficha, arrastra el **PCAP** y el **PPTP**. El análisis se genera automáticamente.
5. **Repite el paso 2** cada día (o cuando quieras): solo se marcan como nuevas las que no habías visto.

> 💡 ¿Quieres verla funcionando? Al abrirla por primera vez, pulsa **«Ver con datos de ejemplo»**.

## Configuración

En la pestaña **Configuración** puedes ajustar:

- Términos del agua, actividades de O&M, CPV y exclusiones del filtro.
- Presupuesto mínimo y máximo, y tipos de contrato.
- Supuestos del estudio de baja (baja media de la competencia, nº de licitadores…).
- Destinatarios del resumen por correo.
- *Opcional:* un modelo de lenguaje (Azure OpenAI u OpenAI) para un análisis más completo de los pliegos.

## Privacidad

- La app funciona **íntegramente en tu navegador**: no hay servidor, ni registro, ni analítica.
- Tus licitaciones, seguimientos, pliegos, notas y claves se guardan **solo en tu navegador**. Si borras los datos de navegación, se pierden: usa **Configuración → Exportar copia**.
- Solo si configuras un modelo de lenguaje se envían fragmentos de los pliegos al servicio que tú elijas.

## Limitaciones

- El navegador no permite leer la Plataforma directamente, así que hay que **descargar el ZIP a mano** (un minuto).
- Las **preguntas y respuestas** se copian y pegan desde la ficha del expediente.
- El filtro trabaja con el título, el CPV y el tipo de contrato: puede colarse o escaparse alguna licitación. Ajusta los términos en Configuración.
- Cobertura: licitaciones publicadas en la Plataforma de Contratación del Sector Público y en las plataformas que agregan en ella.

## ⚠️ Aviso

Herramienta de apoyo, gratuita y distribuida **«tal cual», sin garantía de ningún tipo**. Los análisis, recomendaciones y estudios de baja son automáticos y **orientativos**: pueden contener errores u omisiones y no constituyen asesoramiento jurídico ni económico. **Verifica siempre** en la Plataforma de Contratación y en los pliegos oficiales antes de decidir presentarte. Proyecto personal, sin relación con ningún organismo público.

## 💡 Ideas y mejoras

¡Todas las sugerencias son bienvenidas! Puedes:

- Abrir un **Issue** en este repositorio (*Issues → New issue*).
- Escribirme por **LinkedIn**.

Me interesa especialmente saber qué echas en falta en tu proceso de seguimiento de licitaciones y qué datos de los pliegos te gustaría ver de un vistazo.

## Créditos

Desarrollada por **Carlos Bretón Morales**, ingeniero de ofertas y licitaciones O&M del sector del agua.

Componentes de terceros incluidos:

- [JSZip](https://github.com/Stuk/jszip): licencia MIT (o GPLv3).
- [PDF.js](https://github.com/mozilla/pdf.js) © Mozilla Foundation: licencia Apache 2.0.

Datos: conjuntos de datos abiertos de la Plataforma de Contratación del Sector Público (Ministerio de Hacienda).
