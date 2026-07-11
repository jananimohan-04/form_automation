export default function Shot({ src, caption }) {
  return (
    <div className="max-w-[26rem] px-6 py-5">
      <figure className="m-0">
        <div className="grid aspect-[16/10] place-items-center overflow-hidden rounded-[10px] border border-line bg-bg">
          <img src={src} alt={caption} className="h-full w-full object-contain" />
        </div>
        <figcaption className="mt-2 flex items-center gap-1.5 text-[0.76rem] text-ink-faint">
          <span className="h-px w-2 bg-ink-faint" />
          {caption}
        </figcaption>
      </figure>
    </div>
  );
}
