import VideoCard from './VideoCard';

export default function VideoList({ videos, onSelect }) {
  return (
    <section className="video-list" aria-label="Video list">
      {videos.map(video => (
        <VideoCard key={video.id} video={video} onClick={() => onSelect(video)} />
      ))}
    </section>
  );
}