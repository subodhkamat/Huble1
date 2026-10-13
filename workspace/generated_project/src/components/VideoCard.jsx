export default function VideoCard({ video, onClick }) {
  return (
    <article className="video-card" onClick={onClick} tabIndex="0" role="button" aria-pressed="false">
      <img src={video.thumbnail} alt={`Thumbnail of ${video.title}`} />
      <div className="video-card-content">
        <h3 className="video-card-title">{video.title}</h3>
        <p className="video-card-meta">{video.channel} • {video.views} views</p>
      </div>
    </article>
  );
}