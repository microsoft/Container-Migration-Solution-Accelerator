import React, { useEffect, useRef, useState } from "react";
import { useSelector, useDispatch } from "react-redux";
import { RootState } from "../store/store";
import { togglePanel, closePanel } from "../slices/historyPanelSlice";
declare global {
  interface Window {
    cancelUploads?: () => void;
    cancelLogoUploads?: () => void;
    startTranslating?: () => Promise<string | null>;
  }
}
import {
  Button,
  Tooltip,
} from "@fluentui/react-components";
import Content from "../components/Content/Content";
import Header from "../components/Header/Header";
import HeaderTools from "../components/Header/HeaderTools";
import PanelRightToolbar from "../components/Panels/PanelRightToolbar";
import PanelRight from "../components/Panels/PanelRight";
import "./landingPage.css"

import UploadButton from "../components/uploadButton";
import BatchHistoryPanel from "../components/batchHistoryPanel"
import { HistoryRegular, HistoryFilled, bundleIcon } from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";
import { resetState } from '../slices/batchSlice';
export const History = bundleIcon(HistoryFilled, HistoryRegular);

export const LandingPage = (): JSX.Element => {
  const dispatch = useDispatch(); // Add dispatch hook
  const batchHistoryRef = useRef<{ triggerDeleteAll: () => void } | null>(null);
  const isPanelOpen = useSelector((state: RootState) => state.historyPanel.isOpen);
  const navigate = useNavigate();

  useEffect(() => {
    dispatch(resetState());
  }, [dispatch]);

  const [uploadState, setUploadState] = useState<"IDLE" | "UPLOADING" | "COMPLETED">('IDLE');

  const handleUploadStateChange = (state) => {
    setUploadState(state);
  };

  const handleCancelUploads = () => {
    // This function will be called from BottomBar
    if (window.cancelUploads) {
      window.cancelUploads();
    }
    setUploadState('IDLE');
  };

  const handleStartTranslating = async () => {
    console.log('Starting translation...');

    try {
      if (window.startTranslating) {
        // Get the batchId from startTranslating first
        const resultBatchId = await window.startTranslating();
        navigate('/start');
      //   if (resultBatchId) {
      //     // Once processing is complete, navigate to the modern page
      //     navigate(`/batch-process/${resultBatchId}`);
      //   } else {
      //     // If no batchId returned, just go to modern
      //     navigate("/batch-process");
      //   }
      // } else {
      //   // If startTranslating is not available, just navigate to modern
      //   navigate("/batch-process");
      }
    } catch (error) {
      console.error('Error in handleStartTranslating:', error);
      navigate("/batch-process");
    }
  };



  const handleLeave = () => {
    if (window.cancelLogoUploads) {
      window.cancelLogoUploads();
    }
  };

  const handleTogglePanel = () => {
    console.log("Toggling panel from Landing Page"); // Debugging Log
    dispatch(togglePanel());
  };

  return (
    <div className="landing-page flex flex-col relative h-screen">
      {/* Header */}
      <div onClick={handleLeave} style={{ cursor: "pointer" }}>
        <Header subtitle="Container Migration">
          <div onClick={(e) => e.stopPropagation()}>
            <HeaderTools>
            </HeaderTools>
          </div>
        </Header>
      </div>
      {/* Main Content */}
      <main className={`main-content ${isPanelOpen ? "shifted" : ""} flex-1 flex overflow-auto bg-mode-neutral-background-1-rest relative`}>
        <div className="container mx-auto flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8">
          <Content>
            <div className="w-full max-w-[90vw] sm:max-w-[720px] lg:max-w-[900px] xl:max-w-[1200px]" style={{ zIndex: 950 }}>
              <UploadButton 
                onUploadStateChange={handleUploadStateChange} 
                onStartTranslating={handleStartTranslating}
              />
            </div>
          </Content>
        </div>
      </main>

      {/* Side Panel */}
      {/* Side Panel for History */}

      {isPanelOpen && (
        <div
          style={{
            position: "fixed",
            top: "60px", // Adjust based on your header height
            right: 0,
            height: "calc(100vh - 60px)", // Ensure it does not cover the header
            width: "clamp(260px, 20vw, 320px)", // Responsive width
            zIndex: 1050,
            background: "white",
            //boxShadow: "-2px 0 5px rgba(0, 0, 0, 0.2)", // Optional shadow
            overflowY: "auto",
          }}
        >
          <PanelRight panelWidth={300} panelResize={true} panelType={"first"} >

            <PanelRightToolbar panelTitle="Batch history" panelIcon={<History />} handleDismiss={handleTogglePanel} />
            <BatchHistoryPanel isOpen={isPanelOpen} onClose={() => dispatch(closePanel())} />
          </PanelRight>
        </div>
      )}
    </div>
  );
};

export default LandingPage;